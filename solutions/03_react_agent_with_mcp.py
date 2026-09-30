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
        agent = create_agent(model=model, tools=tools)

        response = await agent.ainvoke({"messages": [{"role": "user", "content": "Which city has the highest total sales amount, and what is that total?"}]})

        print_messages(response)

if __name__ == "__main__":
    asyncio.run(main())
