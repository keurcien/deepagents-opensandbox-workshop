"""Page 8: run code in an OpenSandbox container. No agent, no deepagents.

Before wiring a sandbox into an agent, see what the SDK itself gives you: a
container you can run commands in and copy files to and from. The backend on
the next page is nothing more than these calls behind deepagents' interface.
The SDK is async: every call on the sandbox is awaited. Printing an
`Execution` shows its stdout, a `[stderr]` block, and the exit code on failure.

Run:
    uv run --env-file .env python exercices/08_opensandbox_hello.py

Success: wc reports 1001 lines including the header; the intentional import fails;
the sample downloads and the sandbox is destroyed.

Challenge: Change the generator row count and predict the line count before running.
"""

import asyncio

from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models.filesystem import WriteEntry

# The server address comes from OPEN_SANDBOX_DOMAIN in .env (e.g. http://localhost:7431).
# The server runs in Docker, so sandbox traffic is proxied through it.
SERVER = ConnectionConfig(use_server_proxy=True)

SCRIPT = """\
import csv, random
random.seed(42)
with open("/workspace/orders.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["order_id", "country", "amount"])
    for i in range(1000):
        w.writerow([i, random.choice(["FR", "DE", "ES", "IT", "BE"]), round(random.uniform(5, 500), 2)])
print("wrote /workspace/orders.csv")
"""


async def main() -> None:
    # TODO 1: start a container from the "python:3.12-slim" image with
    #         `await Sandbox.create(image, connection_config=SERVER)` and print its id.
    sandbox = ...

    try:
        # Run a shell command with `await sandbox.commands.run(...)`. The result is an
        # `Execution`: printing it shows stdout, stderr and the exit code.
        print("\n$ uname -a && python3 --version")
        print(await sandbox.commands.run("uname -a && python3 --version"))

        # TODO 2: copy SCRIPT into the container at /workspace/gen.py with
        #         `await sandbox.files.write_files([WriteEntry(path=..., data=<bytes>)])`.
        ...

        # Run it inside the container. The 1000-row CSV never leaves the container.
        print("\n$ python3 /workspace/gen.py")
        print(await sandbox.commands.run("python3 /workspace/gen.py"))

        # TODO 3: ask the container how many lines the CSV has, without reading the
        #         file on this machine.
        ...

        # A failing command: where does the traceback go, what is the exit code?
        print("\n$ python3 -c 'import nope'")
        print(await sandbox.commands.run("python3 -c 'import nope'"))

        # TODO 4: read /workspace/orders.csv back with `await sandbox.files.read_bytes(path)`
        #         and print its first 3 lines.
        ...
    finally:
        # TODO 5: destroy the sandbox (`await sandbox.destroy()`), otherwise the
        #         container lives until its lifetime timeout (10 minutes).
        ...


if __name__ == "__main__":
    asyncio.run(main())
