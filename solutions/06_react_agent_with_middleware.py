import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter
from deepagents.middleware import FilesystemMiddleware

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

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

        # Check for an offloaded result and a targeted file lookup. Avoid reading
        # every row: filesystem tools support retrieval, not bulk computation.
        print_messages(response, max_chars=300)

if __name__ == "__main__":
    asyncio.run(main())
