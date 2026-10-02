import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()
        print("MCP tools:", [t.name for t in tools])

        agent = create_agent(model=model, tools=tools)

        prompt = (
            "This is a deliberately inefficient context-management experiment. "
            "First call execute_sql exactly once with SELECT * FROM orders ORDER BY id "
            "and limit=100000. Do not filter the SQL query or make another SQL call. "
            "Then find order id 99999 and report its date, city, product and amount. "
            "If the result is saved to a file, search that file for the row starting "
            "with [99999, and read only the matching line or a small surrounding window. "
            "Do not read the entire file into context."
        )

        with LiveProgress() as progress:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]}, config={"callbacks": [progress]})

        # Look at the size of the tool result in the panel title.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
