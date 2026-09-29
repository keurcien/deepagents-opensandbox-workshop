import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableConfig
from langchain.mcp import MCPAdapter

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    checkpointer=InMemorySaver()

    config: RunnableConfig = {"configurable": {"thread_id": "1"}}

    mcp_config = {"mcpServers": {"deepwiki": {"url": "https://mcp.deepwiki.com/mcp"}}}


    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()
        agent = create_agent(model=model, tools=tools, checkpointer=checkpointer)

        first_turn_response = await agent.ainvoke({"messages": [{"role": "user", "content": "what is react about?"}]}, config=config)

        print(first_turn_response)

        second_turn_response = await agent.ainvoke({"messages": [{"role": "user", "content": "what did i ask you about?"}]}, config=config)

        print(second_turn_response)

if __name__ == "__main__":
    asyncio.run(main())
