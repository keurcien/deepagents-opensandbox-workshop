"""Page 12: a deep agent with skills injected into the sandbox.

Page 11 gave the agent a shell. Here it also gets a skills library: a directory
of `<skill-name>/SKILL.md` files, each optionally bundling helper scripts. The
library lives on this machine under ./skills and is uploaded into the
container before the agent starts, so the model can both read the instructions
and run the bundled scripts with `execute`.

deepagents' SkillsMiddleware does progressive disclosure: the system prompt
only lists each skill's name and description; the model calls `read_file` on a
SKILL.md when (and only when) the task matches. Watch the trace: it should read
csv-report, ignore release-notes, then run the bundled script instead of
reinventing the report.

Run:
    uv run --env-file .env python solutions/12_deep_agent_skills.py
"""

import importlib
import asyncio
import os
from pathlib import Path

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

# The module name starts with a digit, so a plain `import` cannot name it.
OpenSandboxBackend = importlib.import_module("09_opensandbox_backend").OpenSandboxBackend
from volcamp.pretty import print_messages

LOCAL_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"  # ../skills, shared by exercices/ and solutions/
SANDBOX_SKILLS_DIR = "/skills"

PROMPT = """\
Generate a CSV file at /workspace/orders.csv with 20000 rows and the columns
order_id, country (one of FR, DE, ES, IT, BE at random) and amount (a random
float between 5 and 500, two decimals). Use Python with a fixed random seed of 42.

Then produce a report on that file, grouped by country, and tell me where it is.
"""


async def upload_skills(backend: OpenSandboxBackend, local_dir: Path, remote_dir: str) -> list[str]:
    """Copy every file under local_dir into the sandbox, preserving the layout."""
    files = [
        (f"{remote_dir}/{path.relative_to(local_dir).as_posix()}", path.read_bytes())
        for path in sorted(local_dir.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    ]
    return [response.path for response in await backend.aupload_files(files)]


async def main() -> None:
    model = ChatOpenAI(
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )

    backend = await OpenSandboxBackend.create()  # python:3.12-slim, 10 min lifetime
    print("Sandbox:", backend.id)

    try:
        # 1. Inject the skills library. This happens before the agent exists:
        #    SkillsMiddleware scans the backend for <dir>/SKILL.md at startup.
        for path in await upload_skills(backend, LOCAL_SKILLS_DIR, SANDBOX_SKILLS_DIR):
            print("Uploaded:", path)

        # 2. Point the agent at the directory inside the sandbox.
        agent = create_deep_agent(
            model=model,
            backend=backend,
            skills=[SANDBOX_SKILLS_DIR],
            system_prompt=(
                "You work inside a Linux container. Use the execute tool to run "
                "shell commands and Python. Prefer commands that print only the "
                "numbers you need over reading whole files."
            ),
        )

        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": PROMPT}]},
            config={"recursion_limit": 60},
        )

        print_messages(response, max_chars=400)

        # 3. The report was written by the skill's script, inside the container.
        #    Pull it back to prove the conventions were followed.
        report = (await backend.adownload_files(["/workspace/reports/orders.md"]))[0]
        print("\nReport fetched from the sandbox:\n" + report.content.decode())
    finally:
        await backend.sandbox.destroy()
        print("\nSandbox destroyed.")


if __name__ == "__main__":
    asyncio.run(main())
