"""Page 7: same task, with a deep agent.

Goal: swap `create_agent` for `create_deep_agent`. A deep agent is the react
agent of page 6 with the same filesystem middleware, plus summarization, a
todo list, subagents, skills and a system prompt that knows about them all.
Same MCP server and same SELECT * prompt as pages 5 and 6: compare the tools
the agent got for free.

Run:
    uv run --env-file .env python exercices/07_deep_agent_with_mcp.py
"""

import os
import asyncio
# TODO 1: import `create_deep_agent` from the `deepagents` package.
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()

        # TODO 2: build a deep agent with the same model and tools.
        agent = ...

        prompt = (
            "Run exactly this query with execute_sql: SELECT * FROM orders, with limit=100000 "
            "so that every row comes back in one call. Do not use GROUP BY, count() or sum(): "
            "read the rows yourself, then tell me how many rows there are and the total of the "
            "'amount' column."
        )

        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})

        # The big tool result is offloaded to a file; the model only sees a short notice
        # and then reads the file in chunks. Which tools did the agent get for free?
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
