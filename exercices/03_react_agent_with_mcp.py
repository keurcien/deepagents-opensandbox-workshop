"""Page 3: tools from an MCP server.

Goal: instead of writing tools by hand, load them from an MCP server: the
workshop's own, in volcamp/mcp, which serves orders.csv (100 000 sales rows)
through DuckDB with two tools, get_table_info and execute_sql.

Run:
    uv run --env-file .env python exercices/03_react_agent_with_mcp.py
"""

import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    # TODO 1: describe the MCP server. The shape is
    #         {"mcpServers": {"<name>": {"url": "<streamable http url>"}}}
    #         The workshop server is at http://localhost:7432/mcp
    mcp_config = ...

    async with MCPAdapter(mcp_config) as adapter:
        # TODO 2: list the tools exposed by the server (async call on the adapter).
        tools = ...

        # TODO 3: build the agent with these tools.
        agent = ...

        # MCP tools are async: use `ainvoke`, not `invoke`.
        response = await agent.ainvoke({"messages": [{"role": "user", "content": "Which city has the highest total sales amount, and what is that total?"}]})

        print_messages(response)

if __name__ == "__main__":
    asyncio.run(main())
