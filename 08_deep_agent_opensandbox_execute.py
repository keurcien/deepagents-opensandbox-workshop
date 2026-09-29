"""Page 8: a deep agent that executes commands in an OpenSandbox container.

No MCP server, no spreadsheet. The agent gets a shell inside a container and a
task it cannot answer without running code in it. Watch the `execute` calls go
by and note how little of the generated data ever reaches the model.

Run:
    docker build -t opensandbox-server . && docker run -d --rm -p 8080:8080 \\
        -v /var/run/docker.sock:/var/run/docker.sock \\
        -e OPENSANDBOX_INSECURE_SERVER=YES --name opensandbox opensandbox-server
    uv run --env-file .env python 08_deep_agent_opensandbox_execute.py
"""

import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from opensandbox_backend import OpenSandboxBackend

PROMPT = """\
Generate a CSV file at /workspace/orders.csv with 50000 rows and the columns
order_id, country (one of FR, DE, ES, IT, BE at random) and amount (a random
float between 5 and 500, two decimals). Use Python with a fixed random seed of 42.

Then, without loading the file into your context, tell me:
1. how many rows the file has (excluding the header),
2. the total amount per country, sorted from highest to lowest,
3. the single largest order (its order_id and amount).

Use shell commands or short Python scripts for all of it. Reply with a short
summary, no code."""


def print_trace(messages) -> None:
    """Print each tool call and how large each tool result was."""
    for message in messages:
        if message.type == "ai" and message.tool_calls:
            for call in message.tool_calls:
                args = call["args"]
                shown = args.get("command", args)
                print(f"[tool call] {call['name']}: {shown}")
        elif message.type == "tool":
            text = message.content if isinstance(message.content, str) else str(message.content)
            preview = text[:200].replace("\n", "\n   ")
            print(f"[tool result: {message.name}] {len(text):,} characters\n   {preview}")


def main() -> None:
    model = ChatOpenAI(
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )

    backend = OpenSandboxBackend()  # python:3.12-slim, 10 min lifetime
    print("Sandbox:", backend.id)

    try:
        agent = create_deep_agent(
            model=model,
            backend=backend,
            system_prompt=(
                "You work inside a Linux container. Use the execute tool to run "
                "shell commands and Python. Prefer commands that print only the "
                "numbers you need over reading whole files."
            ),
        )

        response = agent.invoke(
            {"messages": [{"role": "user", "content": PROMPT}]},
            config={"recursion_limit": 60},
        )

        print_trace(response["messages"])
        print("\nFinal answer:\n", response["messages"][-1].content)

        # The file exists in the container, not on this machine. Pull a sample back.
        head = backend.execute("head -3 /workspace/orders.csv").output
        print("\nFirst lines of the file, fetched from the sandbox:\n" + head)
    finally:
        backend.sandbox.destroy()  # otherwise the container lives until the lifetime timeout
        print("\nSandbox destroyed.")


if __name__ == "__main__":
    main()
