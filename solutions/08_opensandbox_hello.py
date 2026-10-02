"""Page 8: run code in an OpenSandbox container. No agent, no deepagents.

Before wiring a sandbox into an agent, see what the SDK itself gives you: a
container you can run commands in and copy files to and from. The backend on
the next page is nothing more than these calls behind deepagents' interface.
The SDK is async: every call on the sandbox is awaited. Printing an
`Execution` shows its stdout, a `[stderr]` block, and the exit code on failure.

Run:
    uv run --env-file .env python solutions/08_opensandbox_hello.py
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
    sandbox = await Sandbox.create("python:3.12-slim", connection_config=OPENSANDBOX_SERVER_CONFIG)
    print("Sandbox:", sandbox.id)

    try:
        print("\n$ uname -a && python3 --version")
        print(await sandbox.commands.run("uname -a && python3 --version"))

        await sandbox.files.write_files([WriteEntry(path="/workspace/gen.py", data=SCRIPT.encode())])

        print("\n$ python3 /workspace/gen.py")
        print(await sandbox.commands.run("python3 /workspace/gen.py"))

        print("\n$ wc -l < /workspace/orders.csv")
        print(await sandbox.commands.run("wc -l < /workspace/orders.csv"))

        print("\n$ python3 -c 'import nope'")
        print(await sandbox.commands.run("python3 -c 'import nope'"))

        content = await sandbox.files.read_bytes("/workspace/orders.csv")
        head = content.decode().splitlines()[:3]
        print("\nFirst lines of orders.csv, read back from the container:")
        print("\n".join("  " + line for line in head))
    finally:
        await sandbox.destroy()
        print("\nSandbox destroyed.")


if __name__ == "__main__":
    asyncio.run(main())
