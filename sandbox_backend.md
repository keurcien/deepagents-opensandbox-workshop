# Writing a sandbox backend for deepagents

deepagents lets an agent work inside any environment that can run shell
commands and move files: a container, a VM, a remote host. You do not write
the file tools. You subclass `BaseSandbox`, implement four members, and
deepagents derives `ls`, `read`, `write`, `edit`, `grep`, `glob` and `delete`
by running shell and Python snippets through your `execute`.

This guide is about that contract. `opensandbox_backend.py` is a worked
example against one provider, and `07_opensandbox_backend_step_by_step.md`
builds it method by method.

```
agent tools        ls  read  write  edit  grep  glob  delete  execute
                    │    │     │     │     │     │      │       │
BaseSandbox         └────┴──┐  │  ┌──┴─────┴─────┴──────┘       │
(derived, yours     python3 │  │  │ python3 / grep / rm         │
 for free)          scripts │  │  │ via execute()               │
                            ▼  ▼  ▼                             ▼
your subclass          execute()   upload_files()   download_files()   id
                            │            │                │
your provider          shell exec    put bytes        get bytes
```

Everything in the two lower rows is yours. Everything above is inherited.

## The four members

```python
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox


class MySandbox(BaseSandbox):
    @property
    def id(self) -> str: ...

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse: ...

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]: ...

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]: ...
```

Python refuses to instantiate the class until all four exist, so write stubs
first and fill them in one at a time.

### `id`

A string that identifies this sandbox instance. It appears in logs and lets
callers correlate a backend with a remote resource. Return whatever your
provider calls the sandbox: a container id, a VM name, a session token.

### `execute(command, *, timeout=None)`

The core primitive. Every derived tool is one or more calls to this method.

**Input.** `command` is a full shell command string. It can be long: the
derived `read` and `glob` send multi-kilobyte `python3 -c "..."` programs. Do
not split it on spaces, do not wrap it in another quoting layer. Hand it to a
POSIX shell as-is.

`timeout` is in seconds. `None` means use your default. `0` may disable the
timeout on backends that allow it. The keyword must appear in your signature:
deepagents inspects `execute` and only forwards a timeout when it finds a
`timeout` parameter. Otherwise it silently drops it.

**Output.** An `ExecuteResponse`:

| Field | Type | Meaning |
|---|---|---|
| `output` | `str` | stdout and stderr, combined |
| `exit_code` | `int \| None` | 0 success, non-zero failure, `None` when unknown |
| `truncated` | `bool` | `True` if your transport clipped the output |

**Rules the derived tools depend on.**

- *Combine stdout and stderr in time order.* If your provider returns them as
  two streams, interleave them by timestamp. Concatenating all of stdout then
  all of stderr puts every error after all the output, which confuses the
  model.
- *Preserve lines exactly.* The derived `grep` parses `path\0line:text`
  records, `ls` and `glob` parse one JSON object per line, `read` parses a
  JSON document. If your provider hands you lines without their trailing
  newline, join them with `"\n"`. Joining with `""` glues records together
  and produces grep matches with NUL bytes in them. Do not strip NUL bytes.
  Do not trim leading whitespace.
- *Never raise.* A provider exception becomes `ExecuteResponse(output=str(exc),
  exit_code=1)`. The model reads the output and decides what to do.
- *Report an unknown exit code as `None`, not 0.* The derived `delete` uses
  `exit_code is not None and exit_code != 0` to decide whether a path exists.
  Faking a 0 makes it report success on a failed command.
- *A timeout is a normal result.* Kill the command, return whatever output you
  have, and use a non-zero or `None` exit code. The convention used by the
  OpenSandbox backend is -1.
- *Set `truncated`* when you know the transport dropped output. `glob` uses it
  to explain why a listing is incomplete.

### `upload_files(files)`

Takes a list of `(absolute_path, bytes)` pairs. Returns one
`FileUploadResponse` per pair, in the same order.

| Field | Meaning |
|---|---|
| `path` | The path you were given, echoed back |
| `error` | `None` on success, otherwise an error code or message |

**Rules.**

- *Partial success.* Catch exceptions per file and put them in the response.
  One bad path must not fail the batch or raise out of the method.
- *Create parent directories.* The docstring is explicit: upload is
  responsible for making sure the parent exists, permissions allowing. The
  derived `write` calls upload with a single file and does not create
  directories itself.
- *Bytes in, bytes on disk.* No encoding, no newline translation.
- *Use the standard error codes* when they fit: `file_not_found`,
  `permission_denied`, `is_directory`, `invalid_path`. They are the
  `FileOperationError` literals and the model is taught what they mean. Fall
  back to a descriptive string for anything else.

### `download_files(paths)`

Takes a list of absolute paths. Returns one `FileDownloadResponse` per path,
in the same order.

| Field | Meaning |
|---|---|
| `path` | The path you were given |
| `content` | `bytes` on success, `None` on failure |
| `error` | `None` on success, otherwise an error code or message |

**Rules.**

- *Partial success*, same as upload. A missing file is
  `FileDownloadResponse(path=p, content=None, error="file_not_found")`, not
  an exception.
- *A directory is an error*, `is_directory`, not an empty payload.
- None of the derived file tools call this. deepagents uses it from the
  memory and skills middleware to load `AGENTS.md`-style files and skill
  definitions out of the sandbox, and your own program uses it to pull
  results back out.

## Lifecycle is yours to design

`BaseSandbox` has no `create`, `close` or `__enter__`. It wraps an
already-running sandbox. Whatever starts and stops the remote resource lives
in your subclass. The pattern that has worked:

```python
class MySandbox(BaseSandbox):
    def __init__(self, handle: ProviderHandle) -> None:
        self._h = handle

    @classmethod
    def create(cls, image: str = "python:3.12-slim", **kwargs) -> "MySandbox":
        return cls(provider.start(image, **kwargs))

    def close(self) -> None:
        self._h.destroy()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
```

Give the sandbox a lifetime on the provider side if it offers one, so a
forgotten `close()` does not leak a container forever. And always close in a
`finally` around the agent run.

## What the image must provide

The derived tools run programs inside the sandbox. If the image lacks them,
the tools fail with a raw traceback or an "unexpected output" error.

| Tool | Runs inside the sandbox | Needs |
|---|---|---|
| `ls` | `python3 -c` using `os.scandir` | `python3` |
| `read` | `python3 -c`, paginated | `python3` |
| `glob` | `python3 -c`, bounded walk (5 s, 10 000 matches) | `python3` |
| `grep` with no glob, or a basename glob like `*.py` | `grep -rHnFZ --include=...` | GNU grep. busybox grep has no `-Z` |
| `grep` with a path glob like `src/**/*.py` | `python3 -c` | `python3` |
| `write` | preflight `python3 -c`, then `upload_files` | `python3` |
| `edit` | `python3 -c`, inline for small payloads, temp files for large | `python3` |
| `delete` | `test -e`, `rm -rf` | POSIX shell and coreutils |

In practice: a POSIX `sh`, GNU coreutils, GNU grep and `python3` on the
`PATH`. `python:3.12-slim` has all of them. Alpine images need
`apk add grep python3`. A scratch or distroless image cannot host a
`BaseSandbox` at all.

## Optional: capture-at-source offload

When a command prints more than the context window should hold, deepagents
can wrap it in a shell script that writes the output to a file inside the
sandbox and returns only a head and tail preview. The full text stays on disk
under `/large_tool_results/` for `read_file`.

This is off by default because the wrapper assumes `sh` with heredocs and
`eval`, plus `mkdir`, `head`, `tail`, `wc`, `cat`, `tr` and `printf`. If your
image has them, opt in:

```python
class MySandbox(BaseSandbox):
    enable_capture_offload = True
```

With it off, large output still gets evicted, but only after a full round
trip through the agent process.

## Optional: native async

Every method has an `a`-prefixed twin: `aexecute`, `aupload_files`, `aread`,
and so on. `BaseSandbox` implements them by running your sync method in a
thread, so you get async for free. If your provider has a real async client,
override `aexecute`, `aupload_files` and `adownload_files` and the derived
async tools use them.

## Skeleton

```python
from __future__ import annotations

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox


def _error_code(exc: Exception) -> str:
    """Map a provider error onto the FileOperationError literals when possible."""
    text = str(exc).lower()
    if "no such file" in text or "not found" in text:
        return "file_not_found"
    if "permission" in text:
        return "permission_denied"
    if "is a directory" in text:
        return "is_directory"
    return f"{type(exc).__name__}: {exc}"


class MySandbox(BaseSandbox):
    def __init__(self, handle) -> None:
        self._h = handle

    @property
    def id(self) -> str:
        return self._h.id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        try:
            result = self._h.run(command, timeout=timeout)
        except Exception as exc:  # provider errors become output, never exceptions
            return ExecuteResponse(output=f"{type(exc).__name__}: {exc}", exit_code=1)
        lines = sorted([*result.stdout, *result.stderr], key=lambda m: m.ts)
        return ExecuteResponse(
            output="\n".join(m.text.rstrip("\n") for m in lines),
            exit_code=result.exit_code,          # None if the provider cannot tell
            truncated=result.output_clipped,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        out = []
        for path, data in files:
            try:
                self._h.mkdir_p(path.rsplit("/", 1)[0] or "/")
                self._h.put(path, data)
                out.append(FileUploadResponse(path=path))
            except Exception as exc:
                out.append(FileUploadResponse(path=path, error=_error_code(exc)))
        return out

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        out = []
        for path in paths:
            try:
                out.append(FileDownloadResponse(path=path, content=self._h.get(path)))
            except Exception as exc:
                out.append(FileDownloadResponse(path=path, error=_error_code(exc)))
        return out
```

Replace `self._h` with your provider's client. The shape of the four methods
does not change.

## Checklist before plugging it into an agent

Run each line and compare with the expected result. Together they exercise
every rule above.

```python
b = MySandbox.create()

# execute: merged streams, exact lines, exit code, timeout
r = b.execute("echo hello; echo err >&2; exit 3")
assert r.output == "hello\nerr" and r.exit_code == 3
assert b.execute("sleep 5", timeout=1).exit_code != 0

# upload: parent dirs, partial success
ups = b.upload_files([("/w/data/a.txt", b"line1\nline2\n"), ("/proc/nope", b"x")])
assert ups[0].error is None and ups[1].error is not None

# download: bytes back, missing file is an error object
d = b.download_files(["/w/data/a.txt", "/nope"])
assert d[0].content == b"line1\nline2\n" and d[1].error == "file_not_found"

# derived tools: if these work, the image and the output format cooperate
print(b.ls("/w/data"))
print(b.read("/w/data/a.txt"))
print(b.grep("line", path="/w/data"))               # two matches, no b'\x00' in text
print(b.grep("line", path="/w", glob="data/*.txt")) # python route
print(b.glob("**/*.txt", path="/w"))
print(b.edit("/w/data/a.txt", "line2", "line3"))
print(b.delete("/w/data/a.txt"))
b.close()
```

Then:

```python
agent = create_deep_agent(model=model, tools=tools, backend=b)
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `TypeError: Can't instantiate abstract class` | One of the four members missing | Add it, even as a stub |
| Timeouts never apply | `timeout` not in your `execute` signature | Add the keyword |
| grep matches contain `\x00`, glob says "unexpected output" | Lines joined with `""` or NULs stripped | Join with `"\n"`, pass output through untouched |
| `ls`, `read`, `glob` return a Python traceback | No `python3` in the image | Use an image that has it |
| `grep` returns nothing or "invalid option" | busybox grep, no `-Z` | Install GNU grep |
| `write` fails on a new directory | `upload_files` did not create the parent | Create it before writing |
| Model sees a stack trace on a missing file | `download_files` raised | Return `error="file_not_found"` |
| `delete` reports success on a failure | Unknown exit code returned as 0 | Return `None` when unknown |
| Every failing command ends with a duplicate error line | Provider error text appended even when the exit code is known | Append only when `exit_code is None` |
