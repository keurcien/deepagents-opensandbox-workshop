"""Optional bonus: let the agent use an API credential without reading it.

Run without an LLM or real credential:
    uv run python solutions/13_deep_agent_credential_vault.py --smoke-test

Run the agent with DEEPSEEK_API_KEY and WORKSHOP_GITHUB_TOKEN set on the host:
    uv run --env-file .env python solutions/13_deep_agent_credential_vault.py

Rebuild the workshop server first: docker compose up --build -d opensandbox
"""

import argparse
import asyncio
import importlib
import os
from contextlib import asynccontextmanager
from datetime import timedelta

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models.sandboxes import (
    Credential,
    CredentialBinding,
    CredentialProxyConfig,
    NetworkPolicy,
    NetworkRule,
)

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

OpenSandboxBackend = importlib.import_module("09_opensandbox_backend").OpenSandboxBackend


@asynccontextmanager
async def credential_backend(token: str, *, host: str, path: str, server: str):
    """Trusted host-side setup. The agent only receives the resulting backend."""
    if not token.strip():
        raise ValueError("The host-side API token must not be empty")
    sandbox = await Sandbox.create(
        "python:3.12-slim",
        connection_config=ConnectionConfig(
            domain=server, use_server_proxy=True, request_timeout=timedelta(seconds=90),
        ),
        ready_timeout=timedelta(seconds=90),
        network_policy=NetworkPolicy(
            defaultAction="deny",
            egress=[NetworkRule(action="allow", target=host)],
        ),
        credential_proxy=CredentialProxyConfig(enabled=True),
    )
    try:
        # The token goes to the sidecar, never to sandbox env/files or agent tools.
        await sandbox.credential_vault.create(
            credentials=[Credential(name="api-token", source={"value": token})],
            bindings=[CredentialBinding(
                name="read-profile",
                match={"schemes": ["https"], "hosts": [host], "methods": ["GET"], "paths": [path]},
                auth={"type": "bearer", "credential": "api-token"},
            )],
        )
        # No deepagents middleware or backend implementation changes are needed.
        yield OpenSandboxBackend(sandbox)
    finally:
        # Also cleans up if vault initialization or the agent fails.
        await sandbox.destroy()


# Only a synthetic token is ever sent to this public echo service. Its response
# includes the token, so print only a boolean, never the response body.
SMOKE_COMMAND = """python3 - <<'PY'
import json
from urllib.request import urlopen
with urlopen("https://httpbin.org/bearer", timeout=30) as response:
    data = json.load(response)
assert data.get("authenticated") is True, "Credential injection did not authenticate"
print("vault authentication succeeded")
PY"""

SMOKE_REVOKED_COMMAND = """python3 - <<'PY'
from urllib.error import HTTPError
from urllib.request import urlopen
try:
    with urlopen("https://httpbin.org/bearer", timeout=30):
        raise AssertionError("Request still authenticated after vault deletion")
except HTTPError as error:
    assert error.code == 401, f"Expected 401 after revocation, got {error.code}"
print("vault revocation succeeded (401)")
PY"""

PROMPT = """Use Python's urllib.request in the sandbox to GET https://api.github.com/user.
Send User-Agent: volcamp-workshop. Authentication is handled by an outbound
credential proxy: do not supply an Authorization header or look for a token.
Print only the login and public profile URL from the JSON response, then summarize.
The sandbox allows network access only to api.github.com. The credential is scoped
to GET /user. Use the installed Python standard library; do not install packages.
Keep TLS certificate verification enabled.
"""


async def main(*, smoke_test: bool, server: str) -> None:
    if smoke_test:
        token, host, path = "volcamp-synthetic-smoke-token", "httpbin.org", "/bearer"
        model = None
    else:
        # Read secrets before creating resources. These values stay on the host.
        token = os.environ["WORKSHOP_GITHUB_TOKEN"]
        host, path = "api.github.com", "/user"
        model = ChatOpenAI(
            model="deepseek-flash", base_url="https://api.deepseek.com",
            api_key=os.environ["DEEPSEEK_API_KEY"],
        )

    async with credential_backend(token, host=host, path=path, server=server) as backend:
        if smoke_test:
            result = await backend.aexecute(SMOKE_COMMAND)
            if result.exit_code != 0:
                raise RuntimeError(f"Vault smoke test failed:\n{result.output}")
            print(result.output)
            await backend.sandbox.credential_vault.delete()
            revoked = await backend.aexecute(SMOKE_REVOKED_COMMAND)
            if revoked.exit_code != 0:
                raise RuntimeError(f"Vault revocation test failed:\n{revoked.output}")
            print(revoked.output)
            return

        agent = create_deep_agent(model=model, backend=backend)
        with LiveProgress() as progress:
            response = await agent.ainvoke(
                {"messages": [{"role": "user", "content": PROMPT}]},
                config={"callbacks": [progress], "recursion_limit": 30},
            )
        print_messages(response, max_chars=400)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-test", action="store_true", help="Use a synthetic token; no LLM or API key needed")
    parser.add_argument("--server", default="localhost:7431", help="OpenSandbox server domain:port")
    args = parser.parse_args()
    asyncio.run(main(smoke_test=args.smoke_test, server=args.server))
