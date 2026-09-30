import os
import asyncio
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()

        agent = create_deep_agent(model=model, tools=tools)

        prompt = (
            "Run exactly this query with execute_sql: SELECT * FROM orders, with limit=100000 "
            "so that every row comes back in one call. Do not use GROUP BY, count() or sum(): "
            "read the rows yourself, then tell me how many rows there are and the total of the "
            "'amount' column."
        )

        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})

        # The big tool result is offloaded to a file; the model only sees a short notice
        # and then reads the file in chunks. Compare the tool result sizes with pages 5 and 6.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
