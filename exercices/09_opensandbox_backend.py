"""Page 9: the OpenSandbox backend for deepagents.

The four members BaseSandbox needs, nothing else. Page 8 showed the SDK
calls; here they go behind deepagents' interface. deepagents derives every file tool (ls,
read_file, write_file, edit_file, grep, glob) from `execute`, so the whole
backend is about fifty lines.

The OpenSandbox SDK is async, and so are the scripts that use this backend
(`agent.ainvoke`). On that path deepagents calls the `a`-prefixed members
(`aexecute`, `aupload_files`, `adownload_files`), so those are the ones to
implement. The sync ones are abstract in BaseSandbox and only stubbed.

Talks to the OpenSandbox server named by OPEN_SANDBOX_DOMAIN in .env
(sandbox traffic is proxied through the server). A sandbox lives 10 minutes unless
destroyed earlier with `await backend.sandbox.destroy()`.

Success: Page 10 can execute a command through the backend and destroy its sandbox.

Challenge: Explain why a virtual filesystem alone cannot execute Python.
"""

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models.filesystem import WriteEntry

# The server address comes from OPEN_SANDBOX_DOMAIN in .env (e.g. http://localhost:7431).
OPENSANDBOX_SERVER_CONFIG = ConnectionConfig(use_server_proxy=True)

class OpenSandboxBackend(BaseSandbox):
    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    @classmethod
    async def create(cls, image: str = "python:3.12-slim") -> "OpenSandboxBackend":  # the image must have python3
        # TODO 1: create the sandbox and return a backend wrapping it. (Creating a
        #         sandbox is a coroutine, which is why this is a classmethod and
        #         not `__init__`.)
        ...

    @property
    def id(self) -> str:
        # TODO 2: return the sandbox id.
        ...

    async def aexecute(self, command: str) -> ExecuteResponse:
        # TODO 3: run `command` in the sandbox and return its output and exit code
        #         as an ExecuteResponse. Careful: the exit code is None on success.
        ...

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        # TODO 4: write every (path, data) pair into the sandbox and return one
        #         FileUploadResponse per file.
        ...

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        # TODO 5: read each path from the sandbox and return one FileDownloadResponse
        #         per path.
        ...

    # BaseSandbox declares the sync members abstract, so they must exist. Nothing calls them under `ainvoke`.
    def execute(self, command: str) -> ExecuteResponse:
        raise NotImplementedError("async backend: invoke the agent with ainvoke")

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        raise NotImplementedError("async backend: use aupload_files")

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        raise NotImplementedError("async backend: use adownload_files")
