"""Page 10: a deep agent that executes commands in an OpenSandbox container.

No MCP server, no spreadsheet. The agent gets a shell inside a container and a
task it cannot answer without running code in it. Watch the `execute` calls go
by and note how little of the generated data ever reaches the model.

Run:
    uv run --env-file .env python exercices/10_deep_agent_opensandbox_execute.py

Success: The agent computes 50,000 rows, country totals and a largest order in code;
the trace does not contain the whole CSV.

Challenge: Have Python independently verify that the country counts sum to 50,000.
"""

import importlib
import asyncio
import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

# The module name starts with a digit, so a plain `import` cannot name it.
OpenSandboxBackend = importlib.import_module("09_opensandbox_backend").OpenSandboxBackend
from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

# TODO 1: write the task. It must force the agent to run code: generate a CSV at
#         /workspace/orders.csv (50 000 rows, columns order_id / country / amount,
#         random seed 42), then, WITHOUT loading the file into its context, report
#         the row count, the total amount per country and the largest order.
PROMPT = """\
...
"""


async def main() -> None:
    model = ChatOpenAI(
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )

    backend = await OpenSandboxBackend.create()  # python:3.12-slim, 10 min lifetime
    print("Sandbox:", backend.id)

    try:
        # TODO 2: build the deep agent with the backend and a system prompt that tells
        #         it it works inside a Linux container, must use the `execute` tool, and
        #         should prefer commands printing only the numbers it needs.
        agent = ...

        with LiveProgress() as progress:
            response = await agent.ainvoke(
                {"messages": [{"role": "user", "content": PROMPT}]},
                config={"callbacks": [progress], "recursion_limit": 60},
            )

        print_messages(response, max_chars=400)

        # TODO 3: the file exists in the container, not on this machine. Download it
        #         through the backend and print its first 3 lines.
        ...
    finally:
        await backend.sandbox.destroy()  # otherwise the container lives until the lifetime timeout
        print("\nSandbox destroyed.")


if __name__ == "__main__":
    asyncio.run(main())
