"""Page 9: the OpenSandbox backend for deepagents.

The four members BaseSandbox needs, nothing else. The OpenSandbox SDK is
async, and so are the scripts that use this backend (`agent.ainvoke`). On that
path deepagents calls the `a`-prefixed members (`aexecute`, `aupload_files`,
`adownload_files`), so those are the ones implemented here. The sync ones are
abstract in BaseSandbox and only stubbed.

Talks to the OpenSandbox server named by OPEN_SANDBOX_DOMAIN in .env
(sandbox traffic is proxied through the server). A sandbox lives 10 minutes unless
destroyed earlier with `await backend.sandbox.destroy()`.
"""

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models.filesystem import WriteEntry

# The server address comes from OPEN_SANDBOX_DOMAIN in .env (e.g. http://localhost:7431).
SERVER = ConnectionConfig(use_server_proxy=True)

class OpenSandboxBackend(BaseSandbox):
    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    @classmethod
    async def create(cls, image: str = "python:3.12-slim") -> "OpenSandboxBackend":  # the image must have python3
        return cls(await Sandbox.create(image, connection_config=SERVER))

    @property
    def id(self) -> str:
        return self.sandbox.id

    async def aexecute(self, command: str) -> ExecuteResponse:
        execution = await self.sandbox.commands.run(command)  # str() gives stdout, then [stderr] and [error] blocks
        return ExecuteResponse(output=str(execution), exit_code=execution.exit_code or 0)

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        await self.sandbox.files.write_files([WriteEntry(path=path, data=data) for path, data in files])
        return [FileUploadResponse(path=path) for path, _ in files]

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [FileDownloadResponse(path=path, content=await self.sandbox.files.read_bytes(path)) for path in paths]

    # BaseSandbox declares the sync members abstract, so they must exist. Nothing calls them under `ainvoke`.
    def execute(self, command: str) -> ExecuteResponse:
        raise NotImplementedError("async backend: invoke the agent with ainvoke")

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        raise NotImplementedError("async backend: use aupload_files")

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        raise NotImplementedError("async backend: use adownload_files")
