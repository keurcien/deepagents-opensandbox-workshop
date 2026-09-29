# The OpenSandbox backend: a walkthrough

This guide is for using the backend. If you want to see how it is built one
method at a time, read `07_opensandbox_backend_step_by_step.md` instead.

## What it is

`opensandbox_backend.py` gives a deepagents agent a real Linux container to
work in. Instead of holding files in memory, the agent uploads, reads, greps
and edits files inside a container, and it gets an `execute` tool that runs
shell commands there. Big tool results (page 6's 100 000-row spreadsheet) land
on the container's disk, and the model pulls out only what it needs with a
command.

The pieces, from the agent down:

```
deep agent  ──tools──▶  OpenSandboxBackend  ──HTTP──▶  OpenSandbox server  ──▶  Docker daemon
                        (opensandbox_backend.py)        (port 8080)               │
                                                                                  ▼
                                                                          sandbox container
                                                                          (python:3.12-slim)
```

The backend never talks to Docker. It talks to the OpenSandbox server through
the `opensandbox` SDK, and the server asks Docker to start, exec into, and
destroy one container per sandbox.

## Prerequisites

- Docker running locally (Docker Desktop on macOS).
- `uv`, with the project synced: `uv sync`. The SDK is already in
  `pyproject.toml` as `opensandbox>=0.1.16`, next to `deepagents`.
- An OpenSandbox server. Two ways to run one are below.

## Step 1: start an OpenSandbox server

### Option A: in a container with the repo's Dockerfile (works today)

```bash
docker build -t opensandbox-server .
docker run --rm -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e OPENSANDBOX_INSECURE_SERVER=YES \
  opensandbox-server
```

The image is the official `opensandbox/server:release-1.1.0` with the Docker
runtime config swapped in. It needs the host's Docker socket because the
sandboxes are started by the host daemon, as siblings of the server container.
Without `server.api_key` in the config the server refuses to start unless you
acknowledge insecure mode with the environment variable above. That is fine
on a laptop, not on a shared machine.

One consequence of running the server in a container: it reports sandbox
addresses on Docker's internal bridge network, which macOS cannot reach. The
SDK must then route sandbox traffic through the server instead of connecting
directly. The backend does not expose that switch yet, so add
`use_server_proxy=True` to the connection config in `OpenSandboxBackend.create`:

```python
config = ConnectionConfigSync(
    domain=...,
    api_key=...,
    protocol=...,
    use_server_proxy=True,   # required when the server runs in a container
)
```

Without it, `create()` fails after 30 seconds with
`SandboxReadyTimeoutException: Sandbox health check timed out`.

### Option B: on the host with uvx (blocked by a packaging bug right now)

```bash
uvx opensandbox-server init-config ~/.sandbox.toml --example docker
OPENSANDBOX_INSECURE_SERVER=YES uvx --from opensandbox-server opensandbox-server --config ~/.sandbox.toml
```

This is the lighter setup and it needs no proxy flag, because a server on the
host can hand out addresses the host can reach. But as of September 2026 the
`opensandbox-server` 1.1.0 wheel on PyPI is missing a generated gRPC module
and dies at startup with `ModuleNotFoundError: ... fast_sandbox.generated`.
Upstream has fixed the packaging on `main`, so this option should work again
with the next release. Until then, use option A.

### Check the server

```bash
curl -s http://localhost:8080/v1/sandboxes
```

The server is up when this returns a JSON object whose `items` array is empty.

## Step 2: point the backend at the server

The backend reads its connection settings from the environment. Put them in
`.env` next to `DEEPSEEK_API_KEY` if they differ from the defaults.

| Variable | Default | Meaning |
|---|---|---|
| `OPENSANDBOX_DOMAIN` | `localhost:8080` | `host:port` of the server |
| `OPENSANDBOX_API_KEY` | unset | Sent when the server has `server.api_key` |
| `OPENSANDBOX_USE_SERVER_PROXY` | unset | `1` when the server runs in Docker (see Dockerfile): sandbox traffic then goes through the server |

## Step 3: first contact

```python
from opensandbox_backend import OpenSandboxBackend

backend = OpenSandboxBackend.create()
try:
    print(backend.id)
    print(backend.execute("uname -a && python3 --version").output)
finally:
    backend.close()
```

What happens:

1. `create()` asks the server for a `python:3.12-slim` container and blocks
   until the container's agent answers a health check. The first run pulls
   the image plus OpenSandbox's `execd` helper image and takes a minute or
   two. After that, a few seconds.
2. `close()` destroys the container.

Two timeouts are involved, and they are easy to confuse:

- **Lifetime** is the `timeout` passed to `SandboxSync.create`, 30 minutes
  in this backend. When it elapses the server kills the sandbox on its own.
  This is the safety net for sandboxes you forgot to close.
- **Ready timeout** is how long `SandboxSync.create` waits for the health
  check, 30 seconds by default in the SDK. Pass `ready_timeout=timedelta(...)`
  if the first image pull is slow.

Always close the backend in a `finally`. Otherwise the container runs until
its lifetime expires.

## Step 4: what the agent can do with it

You implemented four operations. deepagents derives the rest by running shell
and Python snippets through `execute`.

| Tool | Where it runs | Notes |
|---|---|---|
| `execute(command, timeout=)` | `commands.run` in the container | stdout then stderr, one line per message. A timeout kills the command and returns exit code -1. |
| `upload_files([(path, bytes)])` | `files.write_files` | The SDK creates parent directories. |
| `download_files([path])` | `files.read_bytes` | A missing file raises; a production backend would return `error="file_not_found"` instead. |
| `ls`, `read`, `write`, `edit`, `grep`, `glob` | derived by deepagents | Shell and Python one-liners, so the image must have `python3`. |

Try the whole surface once:

```python
backend = OpenSandboxBackend.create()
try:
    backend.upload_files([
        ("/workspace/data/a.txt", b"line1\nline2\n"),
        ("/workspace/data/b.txt", b"x=1\n"),
    ])
    print(backend.ls("/workspace/data"))
    print(backend.read("/workspace/data/a.txt"))
    print(backend.grep("line", path="/workspace/data"))
    print(backend.glob("**/*.txt", path="/workspace"))
    print(backend.edit("/workspace/data/b.txt", "x=1", "x=2"))
    print(backend.execute("cat /workspace/data/b.txt").output)   # x=2
finally:
    backend.close()
```

Every method has an `a`-prefixed async twin (`aexecute`, `aread`, ...), which
deepagents uses when the agent is invoked with `ainvoke`.

## Step 5: plug it into a deep agent

```python
backend = OpenSandboxBackend.create()
try:
    agent = create_deep_agent(model=model, tools=tools, backend=backend)
    response = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
finally:
    backend.close()
```

Compared with the in-memory backend of page 6, two things change:

- **Large tool results are offloaded to the container.** A result that is too
  big for the context window is replaced by a short preview, and the full
  text is written under `/large_tool_results/` inside the sandbox.
- **The agent gets an `execute` tool.** In the test run it answered the
  100 000-row question with one `awk` command over the offloaded file, and
  only the two resulting numbers entered the context window.

The end-to-end demo is `07_deep_agent_opensandbox_backend.py`. It also needs
the Google Sheets MCP server, so set these before running it:

```bash
SPREADSHEET_ID=...              # sheet with ~100 000 rows (see generate_100k_rows.py)
SERVICE_ACCOUNT_PATH=...        # or GOOGLE_APPLICATION_CREDENTIALS
uv run python 07_deep_agent_opensandbox_backend.py
```

The script prints every tool call and the size of every tool result, so you
can watch the offload and the `execute` call happen.

## Step 6: customizing the sandbox

`create()` only takes an image. For anything else, call the SDK yourself and
wrap the result, which is all `create()` does:

```python
from datetime import timedelta
from opensandbox import SandboxSync

sandbox = SandboxSync.create(
    "python:3.12-slim",                 # any image with python3
    connection_config=config,           # same ConnectionConfigSync as in create()
    timeout=timedelta(hours=2),         # lifetime
    ready_timeout=timedelta(minutes=3), # patience for the first pull
    env={"PYTHONUNBUFFERED": "1"},      # environment inside the container
    metadata={"owner": "volcamp"},      # free-form labels, visible on the server
)
backend = OpenSandboxBackend(sandbox)
```

Picking another image:

- It must contain `python3` on the `PATH`. `read` and `glob` are Python
  scripts, and they fail with a Python traceback otherwise.
- Pre-install what the agent will need. Network access from the sandbox
  depends on the server's egress settings, and `pip install` at run time is
  slow and unreliable.
- A custom image only needs to exist on the Docker host. Build it locally
  and pass its tag.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` on `create()` | No server on `OPENSANDBOX_DOMAIN` | Start one (step 1) or fix the variable |
| Server refuses to start | No `server.api_key` in the config | Set one, or `OPENSANDBOX_INSECURE_SERVER=YES` locally |
| `ModuleNotFoundError: ... fast_sandbox.generated` | Broken 1.1.0 wheel on PyPI | Use the Dockerfile (option A) |
| `SandboxReadyTimeoutException` with the Docker server | SDK connects to a bridge IP macOS cannot reach | `use_server_proxy=True` in the connection config |
| `SandboxReadyTimeoutException` on the very first run | Image pull slower than 30 s | Pass a larger `ready_timeout`, or pull the image first |
| `read` or `glob` fail with a Python traceback | Image has no `python3` | Use `python:3.12-slim` or install it |
| Containers pile up in `docker ps` | Backend never closed | Close in `finally`, or wait for the lifetime timeout |
| `execute` returns exit code -1 | Command hit its `timeout` | Raise it, or split the work |
| Authentication error from the server | `server.api_key` set, `OPENSANDBOX_API_KEY` not | Export the key |

To clean up stray sandboxes by hand:

```bash
curl -s http://localhost:8080/v1/sandboxes | python3 -c "import sys,json; print(*(s['id'] for s in json.load(sys.stdin)['items']), sep='\n')"
curl -s -X DELETE http://localhost:8080/v1/sandboxes/<id>
```
