"""Page 5: a tool result that does not fit in the context window.

Goal: with the same MCP server as pages 3 and 4, ask the agent to SELECT * the
whole 100 000-row table in one call. Watch it fail: a plain react agent pastes
every tool result verbatim into the context.

Run:
    uv run --env-file .env python exercices/05_react_agent_context_overflow.py
"""

import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()
        print("MCP tools:", [t.name for t in tools])

        agent = create_agent(model=model, tools=tools)

        # TODO 1: write a prompt that makes the agent run `SELECT * FROM orders`
        #         through execute_sql with limit=100000 (every row in one call),
        #         forbid aggregations (no GROUP BY, count() or sum()), and ask for
        #         the row count and the total of the 'amount' column.
        prompt = ...

        try:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        except Exception as e:
            print(f"\nAgent failed: {type(e).__name__}: {e}\n")
            # TODO 2: explain in one or two printed lines why this failed and what
            #         the next pages do differently (hint: page 6).
            return

        # Look at the size of the tool result in the panel title.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
