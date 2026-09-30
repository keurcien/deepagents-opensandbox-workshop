import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter
from deepagents.middleware import FilesystemMiddleware

from volcamp.pretty import print_messages

async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()

        # Adds ls / read_file / write_file / edit_file / glob / grep, and evicts any
        # tool result above 20 000 tokens to a virtual file (kept in the agent state)
        # that the model reads in chunks.
        agent = create_agent(model=model, tools=tools, middleware=[FilesystemMiddleware()])

        prompt = (
            "Run exactly this query with execute_sql: SELECT * FROM orders, with limit=100000 "
            "so that every row comes back in one call. Do not use GROUP BY, count() or sum(): "
            "read the rows yourself, then tell me how many rows there are and the total of the "
            "'amount' column."
        )

        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})

        # Same plain react agent as page 5, same prompt: now it survives. Look at the
        # size of the execute_sql result and at the tools the middleware added.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
