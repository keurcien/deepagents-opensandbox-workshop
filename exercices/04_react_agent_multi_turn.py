"""Page 4: memory between turns.

Goal: without a checkpointer every `ainvoke` starts from a blank conversation.
Add one, tag both calls with the same thread id, and check that the second
turn remembers the first.

Run:
    uv run --env-file .env python exercices/04_react_agent_multi_turn.py
"""

import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableConfig
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    # TODO 1: create an in-memory checkpointer.
    checkpointer = ...

    # TODO 2: the config that identifies the conversation thread:
    #         {"configurable": {"thread_id": "<any string>"}}
    config: RunnableConfig = ...

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()

        # TODO 3: give the checkpointer to the agent.
        agent = create_agent(model=model, tools=tools)

        # TODO 4: pass `config` to both calls (keyword argument `config=`).
        first_turn_response = await agent.ainvoke({"messages": [{"role": "user", "content": "Which city has the highest total sales amount, and what is that total?"}]})

        print_messages(first_turn_response)

        second_turn_response = await agent.ainvoke({"messages": [{"role": "user", "content": "what did i ask you about?"}]})

        # The checkpointer replays the whole thread: skip what was already printed.
        print_messages(second_turn_response, skip=len(first_turn_response["messages"]))

if __name__ == "__main__":
    asyncio.run(main())
