"""OpenSandbox backend for deepagents.

deepagents ships `BaseSandbox`: implement `execute`, `upload_files`,
`download_files` and `id`, and it derives ls / read / write / edit / grep /
glob on top of them by running shell + python snippets inside the sandbox.
This file plugs the OpenSandbox Python SDK (https://open-sandbox.ai) into that
contract.

Environment:
    OPENSANDBOX_DOMAIN    host:port of the OpenSandbox server (default localhost:8080)
    OPENSANDBOX_API_KEY   API key, if the server requires one
    OPENSANDBOX_PROTOCOL  http (default) or https
    OPENSANDBOX_USE_SERVER_PROXY
                          "1" to route sandbox traffic through the server. Needed when
                          the server runs in a container (see Dockerfile): it reports
                          sandbox addresses on Docker's bridge network, unreachable
                          from the host.
"""

from __future__ import annotations

import os
import posixpath
from datetime import timedelta
from typing import Any

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox
from opensandbox import SandboxSync
from opensandbox.config import ConnectionConfigSync
from opensandbox.exceptions import SandboxException
from opensandbox.models.execd import RunCommandOpts
from opensandbox.models.filesystem import WriteEntry

DEFAULT_IMAGE = "python:3.12-slim"  # BaseSandbox needs python3 in the image for read/glob


def _error_code(exc: Exception) -> str:
    """Map an SDK error onto deepagents' FileOperationError literals when possible."""
    text = str(exc).lower()
    if "no such file" in text or "not found" in text or "404" in text:
        return "file_not_found"
    if "permission" in text or "403" in text:
        return "permission_denied"
    if "is a directory" in text:
        return "is_directory"
    return f"{type(exc).__name__}: {exc}"


class OpenSandboxBackend(BaseSandbox):
    """A deepagents sandbox backend running inside an OpenSandbox container."""

    def __init__(self, sandbox: SandboxSync) -> None:
        self._sandbox = sandbox

    @classmethod
    def create(
        cls,
        image: str = DEFAULT_IMAGE,
        *,
        domain: str | None = None,
        api_key: str | None = None,
        protocol: str | None = None,
        use_server_proxy: bool | None = None,
        timeout: timedelta | None = timedelta(minutes=30),
        **create_kwargs: Any,
    ) -> "OpenSandboxBackend":
        """Start a new sandbox and wrap it. Extra kwargs go to `SandboxSync.create`."""
        config = ConnectionConfigSync(
            domain=domain or os.getenv("OPENSANDBOX_DOMAIN", "localhost:8080"),
            api_key=api_key or os.getenv("OPENSANDBOX_API_KEY"),
            protocol=protocol or os.getenv("OPENSANDBOX_PROTOCOL", "http"),
            use_server_proxy=(
                use_server_proxy
                if use_server_proxy is not None
                else os.getenv("OPENSANDBOX_USE_SERVER_PROXY", "").lower() in ("1", "true", "yes")
            ),
        )
        sandbox = SandboxSync.create(image, connection_config=config, timeout=timeout, **create_kwargs)
        return cls(sandbox)

    # --- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Destroy the remote sandbox."""
        self._sandbox.destroy()

    def __enter__(self) -> "OpenSandboxBackend":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- BaseSandbox contract ------------------------------------------------

    @property
    def id(self) -> str:
        return self._sandbox.id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        opts = RunCommandOpts(timeout=timedelta(seconds=timeout)) if timeout else None
        try:
            execution = self._sandbox.commands.run(command, opts=opts)
        except SandboxException as exc:
            return ExecuteResponse(output=f"{type(exc).__name__}: {exc}", exit_code=1)

        # stdout and stderr arrive as separate streams of line messages (without
        # their trailing newline); interleave them by timestamp so the model sees
        # output in the order it was produced.
        messages = sorted(
            [*execution.logs.stdout, *execution.logs.stderr],
            key=lambda m: m.timestamp,
        )
        output = "\n".join(m.text.rstrip("\n") for m in messages)

        exit_code = execution.exit_code
        if exit_code is None:
            # No exit code means the command did not finish normally; surface why.
            if execution.error:
                output += f"\n[error] {execution.error.name}: {execution.error.value}"
                exit_code = 1
            else:
                exit_code = 0
        return ExecuteResponse(output=output, exit_code=exit_code)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                parent = posixpath.dirname(path)
                if parent and parent != "/":
                    self._sandbox.files.create_directories([WriteEntry(path=parent)])
                self._sandbox.files.write_files([WriteEntry(path=path, data=content, mode=644)])
                responses.append(FileUploadResponse(path=path))
            except Exception as exc:  # noqa: BLE001 - partial success is part of the contract
                responses.append(FileUploadResponse(path=path, error=_error_code(exc)))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                content = self._sandbox.files.read_bytes(path)
                responses.append(FileDownloadResponse(path=path, content=content))
            except Exception as exc:  # noqa: BLE001
                responses.append(FileDownloadResponse(path=path, error=_error_code(exc)))
        return responses
