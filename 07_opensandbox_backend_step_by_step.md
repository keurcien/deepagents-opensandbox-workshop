# Page 7, step by step: building a deepagents backend for OpenSandbox

Page 6 offloaded a 100 000-row tool result into an in-memory filesystem. The
model could page through it, but nothing more. Page 7 swaps that filesystem for
a real container, which gives the model a shell. This guide builds the backend
in `opensandbox_backend.py` one method at a time. The whole file is about
fifty lines.

## 0. Prerequisites

An OpenSandbox server on port 8080, started with the repo's Dockerfile:

```bash
docker build -t opensandbox-server . && docker run -d --rm -p 8080:8080 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -e OPENSANDBOX_INSECURE_SERVER=YES --name opensandbox opensandbox-server
```

Because the server runs in a container, the backend routes sandbox traffic
through the server (`use_server_proxy=True`) rather than connecting to the
sandbox directly.

## 1. Know the contract before writing code

deepagents ships an abstract class, `BaseSandbox`. You implement four members
and it derives everything else (ls, read, write, edit, grep, glob) by running
shell and Python snippets through your `execute`.

```python
class BaseSandbox(SandboxBackendProtocol, ABC):
    @property
    @abstractmethod
    def id(self) -> str: ...

    @abstractmethod
    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse: ...

    @abstractmethod
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]: ...

    @abstractmethod
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]: ...
```

One consequence worth saying out loud: the container image must have
`python3`, because `read` and `glob` are Python scripts executed inside the
sandbox. `python:3.12-slim` is the default for that reason.

Check: open the source and confirm the four abstract methods.

```bash
grep -n "@abstractmethod" -A2 .venv/lib/python3.11/site-packages/deepagents/backends/sandbox.py
```

## 2. Create a sandbox and expose its id

The constructor starts the container. The server address is a constant,
since everyone in the workshop runs the same Dockerfile.

```python
SERVER = ConnectionConfigSync(domain="localhost:8080", use_server_proxy=True)


class OpenSandboxBackend(BaseSandbox):
    def __init__(self, image: str = "python:3.12-slim") -> None:
        self.sandbox = SandboxSync.create(image, connection_config=SERVER)

    @property
    def id(self) -> str:
        return self.sandbox.id
```

`SandboxSync.create` blocks until the container answers a health check. The
first run pulls two images and takes a while. After that, about ten seconds.
The SDK gives each sandbox a 10-minute lifetime, after which the server kills
it on its own. Destroy it earlier with `backend.sandbox.destroy()`.

## 3. `execute`: run a command, hand back one text and an exit code

The SDK call is `self.sandbox.commands.run(command, opts=...)`. It returns an
`Execution` with `logs.stdout`, `logs.stderr` and `exit_code`.

```python
    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        opts = RunCommandOpts(timeout=timedelta(seconds=timeout)) if timeout else None
        execution = self.sandbox.commands.run(command, opts=opts)
        lines = [m.text for m in execution.logs.stdout] + [m.text for m in execution.logs.stderr]
        return ExecuteResponse(output="\n".join(lines), exit_code=execution.exit_code or 0)
```

Two details that are easy to get wrong:

- stdout and stderr are separate lists of messages. The model needs a single
  string, so concatenate them. (Each message carries a timestamp if you want
  to interleave them in production.)
- Each message is one line **without** its trailing newline. Join with `"\n"`.
  Joining with `""` glues lines together and silently breaks deepagents' grep
  and glob parsers, which read the output line by line.

Check:

```python
r = backend.execute("echo hello; echo err >&2; exit 3")
print(repr(r.output), r.exit_code)     # 'hello\nerr' 3
```

## 4. `upload_files`: bytes in

The SDK writes with `files.write_files([WriteEntry(...)])` and creates parent
directories on its own.

```python
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        self.sandbox.files.write_files([WriteEntry(path=path, data=data) for path, data in files])
        return [FileUploadResponse(path=path) for path, _ in files]
```

This is what backs the `write_file` and `edit_file` tools: content never goes
through the shell, so quoting and command-length limits are not a concern.

Check:

```python
print(backend.upload_files([("/workspace/data/a.txt", b"line1\nline2\n")]))
# [FileUploadResponse(path='/workspace/data/a.txt', error=None)]
```

## 5. `download_files`: bytes out

```python
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [FileDownloadResponse(path=path, content=self.sandbox.files.read_bytes(path)) for path in paths]
```

deepagents uses this at startup to read `SKILL.md` and `AGENTS.md` files
(pages 9 and beyond), and you use it yourself to pull results out of the
container. The model's own `read_file` calls do not go through here: `read`
runs a Python snippet via `execute` so only the requested page crosses the
wire.

Check:

```python
print(backend.download_files(["/workspace/data/a.txt"])[0].content)   # b'line1\nline2\n'
```

## 6. The derived tools come for free

Nothing more to write. Run the whole surface once to be sure the image and
the output format cooperate:

```python
backend = OpenSandboxBackend()
try:
    backend.upload_files([("/workspace/data/a.txt", b"line1\nline2\n"), ("/workspace/data/b.txt", b"x=1\n")])
    print(backend.ls("/workspace/data"))
    print(backend.read("/workspace/data/a.txt"))
    print(backend.grep("line", path="/workspace/data"))
    print(backend.glob("**/*.txt", path="/workspace"))
    print(backend.edit("/workspace/data/b.txt", "x=1", "x=2"))
finally:
    backend.sandbox.destroy()
```

If `grep` returns one match whose text contains a NUL byte, or `glob` complains
about "unexpected output", go back to step 3: lines are being glued together.

## 7. Plug it into the deep agent

```python
backend = OpenSandboxBackend()
agent = create_deep_agent(model=model, tools=tools, backend=backend)
```

Two things change compared with page 6, and both are visible in the printed
tool calls:

- Large tool results are still replaced by a "Tool result too large" preview,
  but the file now lives under `/large_tool_results/` **inside the container**.
- The agent has an `execute` tool. In the test run, the model answered the
  100 000-row question with one command instead of paging through the file:

```
awk -F, 'NR==1{next} {n++; s+=$2} END{printf "data_rows=%d\ntotal_amount=%d\n", n, s}' "$f"
```

Only the two resulting numbers entered the context window.

Always destroy the sandbox in a `finally`, or the container lives until the
lifetime `timeout` expires.

## What a production backend adds

This version lets SDK exceptions propagate. The contract expects
`upload_files` and `download_files` to report per-file errors in the response
objects (`error="file_not_found"` and so on) rather than raise, so the model
can recover from a bad path. `execute` should likewise turn a transport error
into an `ExecuteResponse` with a non-zero exit code. That is bookkeeping, not
concept, so it stays out of the workshop.
