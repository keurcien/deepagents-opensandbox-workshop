"""Page 7: the same selective lookup, with a deep agent.

Goal: swap create_agent for create_deep_agent. The harness supplies filesystem
tools, summarization, planning and subagent support. Skills are configured
later on page 11. Compare the trace with page 6: more capabilities do not
necessarily make a simple lookup faster or cheaper.

Run:
    uv run --env-file .env python exercices/07_deep_agent_with_mcp.py

Success: The answer matches page 6; compare model calls, elapsed time and reported tokens.

Challenge: Which added capabilities were actually useful for this simple lookup?
"""

import os
import asyncio
# TODO 1: import create_deep_agent.
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()

        # TODO 2: build a deep agent with the same model and tools.
        agent = ...

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

        # The big tool result is offloaded to a file; the model only sees a short notice
        # and searches for one row. Which tools did the agent get for free?
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
