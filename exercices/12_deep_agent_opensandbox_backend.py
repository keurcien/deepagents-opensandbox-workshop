"""Page 12: a real container as the agent's filesystem.

Final exercise: combine MCP analysis, sandbox execution and artifact download.
Page 7 offloaded the tool result to an in-memory filesystem. Here the
deep agent gets the OpenSandbox container of page 8 instead, which also gives
it a shell. Data still comes from the MCP server of pages 3 to 7; the container
is where the agent builds something with it: a 2-slide deck, pulled back to
this machine at the end.
Fill in `09_opensandbox_backend.py` first (page 9), then plug it in here.

Run:
    uv run --env-file .env python exercices/12_deep_agent_opensandbox_backend.py

Success: sales_analysis.pptx downloads, opens with two slides, and has a native bar
chart. Compare every number and chart label with the SQL aggregates.

Challenge: Ask for a different breakdown and check that the takeaway matches the chart.
"""

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

    # TODO 1: create the backend (this starts a python:3.12-slim container) and
    #         print its id.
    backend = ...

    try:
        async with MCPAdapter(mcp_config) as adapter:
            tools = await adapter.list_tools()

            # TODO 2: hand the backend to the deep agent.
            agent = create_deep_agent(
                model=model,
                tools=tools,
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

        # TODO 3: the deck exists in the container, not on this machine. Download it
        #         and write it to DECK_ON_HOST.
        ...
    finally:
        # TODO 4: destroy the sandbox, otherwise the container lives until its
        #         lifetime timeout.
        ...


if __name__ == "__main__":
    asyncio.run(main())
