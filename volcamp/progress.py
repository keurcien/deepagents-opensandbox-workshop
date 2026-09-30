"""Small live callbacks; keep invoke/ainvoke visible in the workshop scripts."""

from __future__ import annotations

from threading import RLock
from time import monotonic
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from rich.console import Console


class LiveProgress(BaseCallbackHandler):
    """Use as a context manager and pass it in config['callbacks'].

    Events print as calls start/finish, even if invocation subsequently fails.
    Token totals count provider-reported usage once per completed model call;
    missing usage is reported explicitly, rather than estimated as zero.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._lock = RLock()
        self.started = monotonic()
        self.model_calls = 0
        self.tool_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls_with_usage = 0
        self._tools: dict[Any, str] = {}

    def __enter__(self) -> LiveProgress:
        self.started = monotonic()
        self._print("Agent started")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        with self._lock:
            status = "Agent failed" if exc_type else "Agent finished"
            usage = (
                f"{self.input_tokens:,} input / {self.output_tokens:,} output tokens"
                if self.calls_with_usage else "token usage unavailable"
            )
            self._print(
                f"{status}: {self.model_calls} model calls, {self.tool_calls} tool calls; "
                f"{usage} (usage reported for {self.calls_with_usage}/{self.model_calls} calls)"
            )

    def _print(self, message: str) -> None:
        self.console.print(f"[{monotonic() - self.started:6.1f}s] {message}", markup=False)

    def on_chat_model_start(self, serialized: Any, messages: Any, **kwargs: Any) -> None:
        with self._lock:
            self.model_calls += 1
            self._print(f"Model call {self.model_calls} started")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        with self._lock:
            usage = [
                generation.message.usage_metadata
                for batch in response.generations
                for generation in batch
                if getattr(getattr(generation, "message", None), "usage_metadata", None)
            ]
            if usage:
                self.input_tokens += sum(item.get("input_tokens", 0) for item in usage)
                self.output_tokens += sum(item.get("output_tokens", 0) for item in usage)
                self.calls_with_usage += 1
            else:
                reported = (response.llm_output or {}).get("token_usage")
                if reported:
                    self.input_tokens += reported.get("prompt_tokens", 0)
                    self.output_tokens += reported.get("completion_tokens", 0)
                    self.calls_with_usage += 1
            self._print("Model call completed")

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._print(f"Model call failed: {type(error).__name__}")

    def on_tool_start(self, serialized: Any, input_str: str, *, run_id: Any, **kwargs: Any) -> None:
        with self._lock:
            name = (serialized or {}).get("name", "tool")
            self._tools[run_id] = name
            self.tool_calls += 1
            preview = input_str[:160].replace("\n", " ")
            if len(input_str) > 160:
                preview += "…"
            self._print(f"Tool {name} started: {preview}")

    def on_tool_end(self, output: Any, *, run_id: Any, **kwargs: Any) -> None:
        with self._lock:
            name = self._tools.pop(run_id, "tool")
            status = "returned an error" if getattr(output, "status", None) == "error" else "completed"
            content = getattr(output, "content", output)
            detail = ""
            if isinstance(content, str):
                preview = content[:160].replace("\n", " ")
                if len(content) > 160:
                    preview += "…"
                detail = f": {len(content):,} chars; {preview}"
            self._print(f"Tool {name} {status}{detail}")

    def on_tool_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        with self._lock:
            name = self._tools.pop(run_id, "tool")
            self._print(f"Tool {name} failed: {type(error).__name__}")
