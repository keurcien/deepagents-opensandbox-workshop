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
        print("MCP tools:", [t.name for t in tools])

        agent = create_agent(model=model, tools=tools)

        prompt = (
            "Run exactly this query with execute_sql: SELECT * FROM orders, with limit=100000 "
            "so that every row comes back in one call. Do not use GROUP BY, count() or sum(): "
            "read the rows yourself, then tell me how many rows there are and the total of the "
            "'amount' column."
        )

        try:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        except Exception as e:
            print(f"\nAgent failed: {type(e).__name__}: {e}\n")
            print(
                "The tool result is pasted verbatim into the context window, and 100 000 rows\n"
                "do not fit. A plain react agent has no mechanism to deal with this.\n"
                "Next page: the same agent plus a middleware that offloads large tool\n"
                "results to a filesystem and lets the model read them in chunks."
            )
            return

        # Look at the size of the tool result in the panel title.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
