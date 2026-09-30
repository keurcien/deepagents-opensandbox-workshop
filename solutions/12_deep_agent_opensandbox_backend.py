import importlib
import os
import asyncio
from pathlib import Path

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain.mcp import MCPAdapter

# The module name starts with a digit, so a plain `import` cannot name it.
OpenSandboxBackend = importlib.import_module("09_opensandbox_backend").OpenSandboxBackend
from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

DECK_IN_SANDBOX = "/workspace/sales_analysis.pptx"
DECK_ON_HOST = Path(__file__).resolve().parent.parent / "sales_analysis.pptx"

PROMPT = f"""\
Analyse the sales data in the `orders` table with the execute_sql tool: start with
get_table_info, then run a few aggregate queries (for example sales by city, by product,
by month). Never fetch raw rows, only aggregates.

Then build a 2-slide presentation about what you found, at {DECK_IN_SANDBOX}, using
python-pptx inside the container (install it with `pip install python-pptx` first):
  1. a title slide with the two or three headline numbers,
  2. one slide with a native bar chart of the main breakdown, and a one-line takeaway.

Write the script to a file with write_file and run it with the execute tool. Check that the
file exists at the end. Reply with a short summary of the findings, no code."""


async def main():

    model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

    mcp_config = {"mcpServers": {"volcamp_mcp": {"url": "http://localhost:7432/mcp"}}}

    backend = await OpenSandboxBackend.create()  # starts a python:3.12-slim container
    print("Sandbox:", backend.id)

    try:
        async with MCPAdapter(mcp_config) as adapter:
            tools = await adapter.list_tools()

            agent = create_deep_agent(
                model=model,
                tools=tools,
                backend=backend,
                system_prompt=(
                    "You work inside a Linux container with a shell (execute tool) and a "
                    "filesystem. The sales data lives on an MCP server: query it with "
                    "execute_sql, it is not a file in the container."
                ),
            )

            with LiveProgress() as progress:
                response = await agent.ainvoke(
                    {"messages": [{"role": "user", "content": PROMPT}]},
                    config={"callbacks": [progress], "recursion_limit": 60},
                )

            print_messages(response, max_chars=300)

        # The deck exists in the container, not on this machine. Pull it back.
        (deck,) = await backend.adownload_files([DECK_IN_SANDBOX])
        DECK_ON_HOST.write_bytes(deck.content)
        print(f"\nDownloaded {DECK_IN_SANDBOX} to {DECK_ON_HOST} ({len(deck.content):,} bytes)")
    finally:
        await backend.sandbox.destroy()  # otherwise the container lives until the lifetime timeout
        print("Sandbox destroyed.")


if __name__ == "__main__":
    asyncio.run(main())
