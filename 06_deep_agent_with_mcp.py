import os
import asyncio
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

# Page 6: same task as page 5, but with deepagents.
#
# `create_deep_agent` wraps the react loop with middleware. The one that matters
# here is FilesystemMiddleware: any tool result above ~20 000 tokens is NOT put
# in the context window. It is written to a virtual filesystem (in-memory
# StateBackend by default) and the model only receives a head/tail preview plus
# the file path. The model then reads the file in chunks with `read_file`
# (offset + limit), or greps it, instead of swallowing 100 000 rows at once.
#
# Same setup as page 5 (big sheet imported, SPREADSHEET_ID in .env, Google auth).


async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    spreadsheet_id = os.environ["SPREADSHEET_ID"]

    sheets_env = {
        key: os.environ[key]
        for key in ("SERVICE_ACCOUNT_PATH", "DRIVE_FOLDER_ID", "GOOGLE_APPLICATION_CREDENTIALS")
        if os.getenv(key)
    }

    mcp_config = {
        "mcpServers": {
            "sheets": {
                "command": "uvx",
                "args": ["--with", "mcp<2", "mcp-google-sheets@latest"],
                "env": sheets_env,
            }
        }
    }

    async with MCPAdapter(mcp_config) as adapter:
        tools = await adapter.list_tools()

        agent = create_deep_agent(model=model, tools=tools)

        prompt = (
            f"Download the entire content of sheet 'Sheet1' in spreadsheet {spreadsheet_id}. "
            "It has about 100000 rows. Read ALL the rows, then tell me how many rows there are "
            "and what the total of the 'amount' column is."
        )

        response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})

        # Watch the tool messages: the get_sheet_data result is replaced by
        # "Tool result too large, ... saved in the filesystem at this path: ..."
        # followed by read_file calls on that path.
        for message in response["messages"]:
            if message.type == "ai" and message.tool_calls:
                print(f"[tool call] {[(c['name'], c['args']) for c in message.tool_calls]}")
            if message.type == "tool":
                text = message.content if isinstance(message.content, str) else str(message.content)
                print(f"[tool result: {message.name}] {len(text):,} characters")
                print("   " + text[:300].replace("\n", "\n   "))

        print("\nFinal answer:", response["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
