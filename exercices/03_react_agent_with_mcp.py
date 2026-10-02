"""Page 3: tools from an MCP server.

Goal: instead of writing tools by hand, load them from an MCP server: the
workshop's own, in volcamp/mcp, which serves orders.csv (100 000 sales rows)
through DuckDB with two tools, get_table_info and execute_sql.

Run:
    uv run --env-file .env python exercices/03_react_agent_with_mcp.py

Success: The answer is Paris, with total sales of 13,986,204.84.

Challenge: Ask for the top three cities and inspect the SQL used.
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

    # TODO 1: describe the workshop MCP server (see the slide for its URL).
    mcp_config = ...

    async with MCPAdapter(mcp_config) as adapter:
        # TODO 2: list the tools exposed by the server.
        tools = ...

        # TODO 3: build the agent with these tools.
        agent = ...

        # MCP tools are async: use `ainvoke`, not `invoke`.
        with LiveProgress() as progress:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": "Which city has the highest total sales amount, and what is that total?"}]}, config={"callbacks": [progress]})

        print_messages(response)

if __name__ == "__main__":
    asyncio.run(main())
