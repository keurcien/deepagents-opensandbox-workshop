"""OpenSandbox backend for deepagents: the four members BaseSandbox needs, nothing else.

Talks to the server started from the Dockerfile (localhost:8080, sandbox
traffic proxied through the server). A sandbox lives 10 minutes unless
destroyed earlier with `backend.sandbox.destroy()`.
"""

from datetime import timedelta

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync
from opensandbox.models.execd import RunCommandOpts
from opensandbox.models.filesystem import WriteEntry

SERVER = ConnectionConfigSync(domain="localhost:8080", use_server_proxy=True)


class OpenSandboxBackend(BaseSandbox):
    def __init__(self, image: str = "python:3.12-slim") -> None:  # the image must have python3
        self.sandbox = SandboxSync.create(image, connection_config=SERVER)

    @property
    def id(self) -> str:
        return self.sandbox.id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        opts = RunCommandOpts(timeout=timedelta(seconds=timeout)) if timeout else None
        execution = self.sandbox.commands.run(command, opts=opts)
        lines = [m.text for m in execution.logs.stdout + execution.logs.stderr]
        return ExecuteResponse(output="\n".join(lines), exit_code=execution.exit_code or 0)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        self.sandbox.files.write_files([WriteEntry(path=path, data=data) for path, data in files])
        return [FileUploadResponse(path=path) for path, _ in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [FileDownloadResponse(path=path, content=self.sandbox.files.read_bytes(path)) for path in paths]
