"""Page 8: run code in an OpenSandbox container. No agent, no deepagents.

Before wiring a sandbox into an agent, see what the SDK itself gives you: a
container you can run commands in and copy files to and from. The backend on
the next page is nothing more than these calls behind deepagents' interface.
The SDK is async: every call on the sandbox is awaited. Printing an
`Execution` shows its stdout, a `[stderr]` block, and the exit code on failure.

Run:
    uv run --env-file .env python exercices/08_opensandbox_hello.py

Success: ls shows gen.py and orders.csv in /workspace; the intentional import fails;
the first three CSV lines print and the sandbox is destroyed.

Challenge: Change the CSV filename in the generator and check that ls reflects it.
"""

import asyncio

from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models.filesystem import WriteEntry

# The server address comes from OPEN_SANDBOX_DOMAIN in .env (e.g. http://localhost:7431).
# The server runs in Docker, so sandbox traffic is proxied through it.
OPENSANDBOX_SERVER_CONFIG = ConnectionConfig(use_server_proxy=True)

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
    #         `await Sandbox.create(image, connection_config=OPENSANDBOX_SERVER_CONFIG)` and print its id.
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

        # TODO 3: list the contents of /workspace with a shell command, without
        #         touching the filesystem on this machine.
        ...

        # A failing command: where does the traceback go, what is the exit code?
        print("\n$ python3 -c 'import nope'")
        print(await sandbox.commands.run("python3 -c 'import nope'"))

        # TODO 4: print the first 3 lines of /workspace/orders.csv with a shell command.
        ...
    finally:
        # TODO 5: destroy the sandbox (`await sandbox.destroy()`), otherwise the
        #         container lives until its lifetime timeout (10 minutes).
        ...


if __name__ == "__main__":
    asyncio.run(main())
