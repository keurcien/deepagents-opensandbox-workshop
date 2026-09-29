import os
import asyncio
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

# Page 5: what happens when an MCP tool returns way too much data?
#
# The agent is connected to a Google Sheets MCP server and asked to fetch a
# sheet containing 100 000 rows. Every tool result is injected verbatim into
# the model's context window, so a single `get_sheet_data` call on the full
# sheet produces millions of tokens and the provider rejects the request
# (context length exceeded). There is no fix inside a plain react agent:
# page 6 solves it with deepagents.
#
# Setup:
#   1. Generate the data:        uv run generate_100k_rows.py
#   2. Import big_sheet.csv into a new Google Sheet (File > Import).
#   3. Auth, either:
#        - gcloud Application Default Credentials (already on this machine):
#            gcloud auth application-default login \
#              --scopes=https://www.googleapis.com/auth/spreadsheets.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/cloud-platform
#        - or a service account: share the sheet with its email (Viewer) and set
#            SERVICE_ACCOUNT_PATH=/absolute/path/to/service-account.json
#   4. Set in .env:
#        SPREADSHEET_ID=<id from the sheet URL>
#
# MCP server used: https://github.com/xing5/mcp-google-sheets (run through uvx).
# It still targets mcp 1.x, hence the `--with mcp<2` pin below.


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
        print("MCP tools:", [t.name for t in tools])

        agent = create_agent(model=model, tools=tools)

        prompt = (
            f"Download the entire content of sheet 'Sheet1' in spreadsheet {spreadsheet_id}. "
            "It has about 100000 rows. Read ALL the rows, then tell me how many rows there are "
            "and what the total of the 'amount' column is."
        )

        try:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        except Exception as e:
            print(f"\nAgent failed: {type(e).__name__}: {e}\n")
            print(
                "The tool result is pasted verbatim into the context window, and 100 000 rows\n"
                "do not fit. A plain react agent has no mechanism to deal with this.\n"
                "Next page: the same task with deepagents, which offloads large tool results\n"
                "to a filesystem and lets the model read them in chunks."
            )
            return

        # If the provider did accept the request, show how much of the context the rows ate.
        for message in response["messages"]:
            if message.type == "tool":
                print(f"[tool result] {len(message.content):,} characters (~{len(message.content) // 4:,} tokens)")

        print("\nFinal answer:", response["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
