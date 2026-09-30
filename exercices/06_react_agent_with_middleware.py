"""Page 6: offload a large result and retrieve only what matters.

Goal: add FilesystemMiddleware to the page 5 agent. Large tool results are
saved to a virtual file in agent state (default threshold: roughly 20 000
tokens). The agent can search that file and read a small relevant portion.
Offloading does not compute totals or make reading all 100 000 rows efficient.
For a real order lookup, use a WHERE clause in SQL; this forced full-table
fetch exists only to demonstrate context management.

Run:
    uv run --env-file .env python exercices/06_react_agent_with_middleware.py

Success: The trace shows offloading, a targeted file lookup, and order 99999:
2025-01-21, Lyon, webcam, 47.24.

Challenge: Compare how much data the model sees with page 5; do not read the full file.
"""

import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter
# TODO 1: import FilesystemMiddleware from `deepagents.middleware`.

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()

        # TODO 2: pass `middleware=[FilesystemMiddleware()]` to create_agent.
        agent = create_agent(model=model, tools=tools)

        prompt = (
            "This is a deliberately inefficient context-management experiment. "
            "First call execute_sql exactly once with SELECT * FROM orders ORDER BY id "
            "and limit=100000. Do not filter the SQL query or make another SQL call. "
            "Then find order id 99999 and report its date, city, product and amount. "
            "If the result is saved to a file, search that file for the row starting "
            "with [99999, and read only the matching line or a small surrounding window. "
            "Do not read the entire file into context."
        )

        with LiveProgress() as progress:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": [progress]})

        # Check for an offloaded result and a targeted file lookup. Avoid reading
        # every row: filesystem tools support retrieval, not bulk computation.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
