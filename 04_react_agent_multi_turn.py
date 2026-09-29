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
        # read_wiki_contents returns a whole wiki (1.2 MB for facebook/react) in a
        # single SSE event, above the MCP client's 1 MiB cap, which surfaces as
        # "SSE stream ended without a response". The other tools return small
        # answers, so leave the big dump out.
        tools = [tool for tool in tools if tool.name != "read_wiki_contents"]
        agent = create_agent(model=model, tools=tools, checkpointer=checkpointer)

        first_turn_response = await agent.ainvoke({"messages": [{"role": "user", "content": "what is react about?"}]}, config=config)

        print(first_turn_response)

        second_turn_response = await agent.ainvoke({"messages": [{"role": "user", "content": "what did i ask you about?"}]}, config=config)

        print(second_turn_response)

if __name__ == "__main__":
    asyncio.run(main())
