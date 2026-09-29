# Page 7, step by step: building a deepagents backend for OpenSandbox

Page 6 offloaded a 100 000-row tool result into an in-memory filesystem. The
model could page through it, but nothing more. Page 7 swaps that filesystem for
a real container, which gives the model a shell. This guide builds the backend
in `opensandbox_backend.py` one method at a time. Each step ends with a check
you can run.

## 0. Prerequisites

An OpenSandbox server, running locally on port 8080:

```bash
uvx opensandbox-server init-config ~/.sandbox.toml --example docker
OPENSANDBOX_INSECURE_SERVER=YES uvx opensandbox-server   # or set server.api_key in the toml
```

The SDK in the project:

```bash
uv add opensandbox
```

## 1. Know the contract before writing code

deepagents ships an abstract class, `BaseSandbox`. You implement four things and
it derives everything else (ls, read, write, edit, grep, glob) by running shell
and Python snippets through your `execute`.

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

Two consequences worth saying out loud:

- The container image must have `python3`. `read` and `glob` are Python scripts
  executed inside the sandbox. `python:3.12-slim` is the default for that reason.
- `upload_files` and `download_files` must never raise. They report per-file
  errors in the response objects so the model can recover.

Check: open the source and confirm the four abstract methods.

```bash
grep -n "@abstractmethod" -A2 .venv/lib/python3.11/site-packages/deepagents/backends/sandbox.py
```

## 2. Create a sandbox and expose its id

Start with the skeleton. Connection settings come from the environment so the
same code works against a local server or a hosted one.

```python
import os
from datetime import timedelta

from deepagents.backends.sandbox import BaseSandbox
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync

DEFAULT_IMAGE = "python:3.12-slim"


class OpenSandboxBackend(BaseSandbox):
    def __init__(self, sandbox: SandboxSync) -> None:
        self._sandbox = sandbox

    @classmethod
    def create(cls, image: str = DEFAULT_IMAGE, *, timeout=timedelta(minutes=30), **create_kwargs):
        config = ConnectionConfigSync(
            domain=os.getenv("OPENSANDBOX_DOMAIN", "localhost:8080"),
            api_key=os.getenv("OPENSANDBOX_API_KEY"),
            protocol=os.getenv("OPENSANDBOX_PROTOCOL", "http"),
        )
        sandbox = SandboxSync.create(image, connection_config=config, timeout=timeout, **create_kwargs)
        return cls(sandbox)

    def close(self) -> None:
        self._sandbox.destroy()

    @property
    def id(self) -> str:
        return self._sandbox.id
```

`SandboxSync.create` blocks until the container answers a health check. The
`timeout` is the sandbox lifetime, after which the server kills it on its own.
Python will refuse to instantiate the class until the other three abstract
methods exist, so for this check call the SDK directly:

```python
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync

sb = SandboxSync.create("python:3.12-slim", connection_config=ConnectionConfigSync(domain="localhost:8080", protocol="http"))
print(sb.id)
sb.destroy()
```

The first run pulls two images and takes a while. After that, about ten seconds.

## 3. `execute`: run a command and normalize the result

The SDK call is `self._sandbox.commands.run(command, opts=...)`. It returns an
`Execution` with `logs.stdout`, `logs.stderr`, `exit_code` and `error`.

```python
from deepagents.backends.protocol import ExecuteResponse
from opensandbox.exceptions import SandboxException
from opensandbox.models.execd import RunCommandOpts

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        opts = RunCommandOpts(timeout=timedelta(seconds=timeout)) if timeout else None
        try:
            execution = self._sandbox.commands.run(command, opts=opts)
        except SandboxException as exc:
            return ExecuteResponse(output=f"{type(exc).__name__}: {exc}", exit_code=1)

        messages = sorted(
            [*execution.logs.stdout, *execution.logs.stderr],
            key=lambda m: m.timestamp,
        )
        output = "\n".join(m.text.rstrip("\n") for m in messages)

        exit_code = execution.exit_code
        if exit_code is None:
            if execution.error:
                output += f"\n[error] {execution.error.name}: {execution.error.value}"
                exit_code = 1
            else:
                exit_code = 0
        return ExecuteResponse(output=output, exit_code=exit_code)
```

Three details that are easy to get wrong:

- stdout and stderr are separate lists. Merge them by timestamp or the model
  sees all errors after all output.
- Each message is one line **without** its trailing newline. Join with `"\n"`.
  Joining with `""` glues lines together and silently breaks deepagents' grep
  and glob parsers, which read the output line by line. This bug was found
  while building this page.
- A non-zero exit sets both `exit_code` and an `error` named
  `CommandExecError`. Only append the error text when there is no exit code,
  otherwise every failing command gets a redundant `[error]` line.

Check, once the two stubs below exist so the class can be instantiated:

```python
r = backend.execute("echo hello; echo err >&2; exit 3")
print(repr(r.output), r.exit_code)     # 'hello\nerr' 3
print(backend.execute("sleep 5", timeout=1).exit_code)   # -1, killed by the server
```

## 4. `upload_files`: write bytes, create parents, never raise

The SDK writes with `files.write_files([WriteEntry(...)])`. Two things the
contract asks for that the SDK does not do on its own: create the parent
directory, and catch errors per file.

```python
import posixpath
from deepagents.backends.protocol import FileUploadResponse
from opensandbox.models.filesystem import WriteEntry

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses = []
        for path, content in files:
            try:
                parent = posixpath.dirname(path)
                if parent and parent != "/":
                    self._sandbox.files.create_directories([WriteEntry(path=parent)])
                self._sandbox.files.write_files([WriteEntry(path=path, data=content, mode=644)])
                responses.append(FileUploadResponse(path=path))
            except Exception as exc:
                responses.append(FileUploadResponse(path=path, error=_error_code(exc)))
        return responses
```

`WriteEntry.mode` defaults to 755. Pass 644 for data files.

`_error_code` maps SDK exceptions onto the four literals deepagents
understands: `file_not_found`, `permission_denied`, `is_directory`,
`invalid_path`. Anything else falls back to the exception text.

```python
def _error_code(exc: Exception) -> str:
    text = str(exc).lower()
    if "no such file" in text or "not found" in text or "404" in text:
        return "file_not_found"
    if "permission" in text or "403" in text:
        return "permission_denied"
    if "is a directory" in text:
        return "is_directory"
    return f"{type(exc).__name__}: {exc}"
```

Check:

```python
print(backend.upload_files([("/workspace/data/a.txt", b"line1\nline2\n")]))
# [FileUploadResponse(path='/workspace/data/a.txt', error=None)]
```

## 5. `download_files`: read bytes, report missing files

```python
from deepagents.backends.protocol import FileDownloadResponse

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses = []
        for path in paths:
            try:
                content = self._sandbox.files.read_bytes(path)
                responses.append(FileDownloadResponse(path=path, content=content))
            except Exception as exc:
                responses.append(FileDownloadResponse(path=path, error=_error_code(exc)))
        return responses
```

Check. A missing file must come back as an error object, not an exception:

```python
print(backend.download_files(["/workspace/data/a.txt", "/nope.txt"]))
# [... content=b'line1\nline2\n' ..., FileDownloadResponse(path='/nope.txt', content=None, error='file_not_found')]
```

## 6. The derived tools come for free

Nothing more to write. `BaseSandbox` now provides the rest. Run the whole
surface once to be sure the image and the output format cooperate:

```python
with OpenSandboxBackend.create() as backend:          # add __enter__/__exit__ calling close()
    backend.upload_files([("/workspace/data/a.txt", b"line1\nline2\n"), ("/workspace/data/b.txt", b"x=1\n")])
    print(backend.ls("/workspace/data"))
    print(backend.read("/workspace/data/a.txt"))
    print(backend.grep("line", path="/workspace/data"))
    print(backend.glob("**/*.txt", path="/workspace"))
    print(backend.edit("/workspace/data/b.txt", "x=1", "x=2"))
```

If `grep` returns one match whose text contains a NUL byte, or `glob` complains
about "unexpected output", go back to step 3: lines are being glued together.

## 7. Plug it into the deep agent

```python
backend = OpenSandboxBackend.create()
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

## Recap of the gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Server refuses to start | No `server.api_key` in `~/.sandbox.toml` | Set one, or `OPENSANDBOX_INSECURE_SERVER=YES` locally |
| `read` or `glob` fail with a Python error | Image has no `python3` | Use `python:3.12-slim` or install it |
| grep matches contain `\x00`, glob "unexpected output" | Output lines joined with `""` | Join messages with `"\n"` |
| Every failing command ends with `[error] CommandExecError` | Error appended even when exit code is known | Append only when `exit_code is None` |
| Upload fails on a new directory | SDK does not create parents | `create_directories` before `write_files` |
| Model sees an exception traceback on a missing file | `download_files` raised | Return `error="file_not_found"` instead |
