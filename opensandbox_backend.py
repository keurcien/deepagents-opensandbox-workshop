"""OpenSandbox backend for deepagents, reduced to what the contract needs.

deepagents' `BaseSandbox` has four abstract members: `id`, `execute`,
`upload_files` and `download_files`. Everything the agent sees as file tools
(ls, read_file, write_file, edit_file, grep, glob) is derived from those four
by running shell and Python snippets through `execute`.

Environment:
    OPENSANDBOX_DOMAIN             server host:port (default localhost:8080)
    OPENSANDBOX_API_KEY            if the server requires one
    OPENSANDBOX_USE_SERVER_PROXY   "1" when the server runs in Docker (see Dockerfile)
"""

import os
from datetime import timedelta

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync
from opensandbox.models.execd import RunCommandOpts
from opensandbox.models.filesystem import WriteEntry


class OpenSandboxBackend(BaseSandbox):
    def __init__(self, sandbox: SandboxSync) -> None:
        self._sandbox = sandbox

    @classmethod
    def create(cls, image: str = "python:3.12-slim") -> "OpenSandboxBackend":
        """Start a container and wrap it. The image must have python3 for read_file/glob."""
        config = ConnectionConfigSync(
            domain=os.getenv("OPENSANDBOX_DOMAIN", "localhost:8080"),
            api_key=os.getenv("OPENSANDBOX_API_KEY"),
            use_server_proxy=os.getenv("OPENSANDBOX_USE_SERVER_PROXY") == "1",
        )
        return cls(SandboxSync.create(image, connection_config=config, timeout=timedelta(minutes=30)))

    def close(self) -> None:
        self._sandbox.destroy()

    @property
    def id(self) -> str:
        return self._sandbox.id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        opts = RunCommandOpts(timeout=timedelta(seconds=timeout)) if timeout else None
        execution = self._sandbox.commands.run(command, opts=opts)
        # stdout and stderr arrive as separate lists of lines; the model gets one text.
        lines = [m.text for m in execution.logs.stdout] + [m.text for m in execution.logs.stderr]
        return ExecuteResponse(output="\n".join(lines), exit_code=execution.exit_code or 0)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        self._sandbox.files.write_files([WriteEntry(path=path, data=data) for path, data in files])
        return [FileUploadResponse(path=path) for path, _ in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [FileDownloadResponse(path=path, content=self._sandbox.files.read_bytes(path)) for path in paths]
