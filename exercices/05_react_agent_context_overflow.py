"""Page 5: an oversized tool result, deliberately fetched in full.

Goal: request all 100 000 rows before locating one order. This intentionally
bad baseline can exceed the model's context window. The live trace survives
failure. A context rejection is expected, but depends on the model; a timeout,
authentication error or rate limit is a setup problem, not the lesson.

Run:
    uv run --env-file .env python exercices/05_react_agent_context_overflow.py

Success: The trace shows the full-table query and its result before any context rejection.

Challenge: Explain why a filtered SQL query would avoid this artificial failure.
"""

import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()
        print("MCP tools:", [t.name for t in tools])

        agent = create_agent(model=model, tools=tools)

        # TODO 1: ask for SELECT * FROM orders ORDER BY id with limit=100000 in
        #         exactly one execute_sql call, then locate order id 99999 and
        #         report its date, city, product and amount. Forbid filtered SQL
        #         and further SQL calls. Page 6 supplies the comparison prompt.
        prompt = ...

        with LiveProgress() as progress:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": [progress]})

        # Look at the size of the tool result in the panel title.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
