import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"deepwiki": {"url": "https://mcp.deepwiki.com/mcp"}}}


    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()
        agent = create_agent(model=model, tools=tools)

        response = await agent.ainvoke({"messages": [{"role": "user", "content": "what is react about?"}]})

        print(response)


if __name__ == "__main__":
    asyncio.run(main())
