import os
import asyncio
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

from opensandbox_backend import OpenSandboxBackend

# Page 7: same task, but the deep agent's filesystem is a real sandbox.
#
# Page 6 offloaded the 100 000 rows into an in-memory virtual filesystem
# (StateBackend). The model could only page through it with read_file.
#
# Here the backend is an OpenSandbox container (see opensandbox_backend.py).
# Two things change:
#   - large tool results are written to a real file inside the container
#   - deepagents exposes an `execute` tool, so the model can run a shell
#     command or a Python one-liner over the file and get the answer in one
#     call, instead of reading 100 000 lines through the context window.
#
# Setup, on top of page 5: an OpenSandbox server on localhost:8080, started
# from the repo's Dockerfile:
#   docker build -t opensandbox-server . && docker run -d --rm -p 8080:8080 \
#       -v /var/run/docker.sock:/var/run/docker.sock \
#       -e OPENSANDBOX_INSECURE_SERVER=YES --name opensandbox opensandbox-server


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

    backend = OpenSandboxBackend()  # starts a python:3.12-slim container
    print("Sandbox:", backend.id)

    try:
        async with MCPAdapter(mcp_config) as adapter:
            tools = await adapter.list_tools()

            agent = create_deep_agent(model=model, tools=tools, backend=backend)

            prompt = (
                f"Download the entire content of sheet 'Sheet1' in spreadsheet {spreadsheet_id}. "
                "It has about 100000 rows. Read ALL the rows, then tell me how many rows there are "
                "and what the total of the 'amount' column is."
            )

            response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})

            for message in response["messages"]:
                if message.type == "ai" and message.tool_calls:
                    print(f"[tool call] {[(c['name'], c['args']) for c in message.tool_calls]}")
                if message.type == "tool":
                    text = message.content if isinstance(message.content, str) else str(message.content)
                    print(f"[tool result: {message.name}] {len(text):,} characters")
                    print("   " + text[:300].replace("\n", "\n   "))

            print("\nFinal answer:", response["messages"][-1].content)
    finally:
        backend.sandbox.destroy()


if __name__ == "__main__":
    asyncio.run(main())
