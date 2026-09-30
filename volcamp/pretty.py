"""Pretty-print a LangChain / deepagents conversation.

    from volcamp.pretty import print_messages

    response = agent.invoke({"messages": [...]})
    print_messages(response)

Each message becomes a colored panel: the human prompt, the model's reasoning
(optional), its tool calls with their arguments, every tool result with its
size in characters and tokens, and the final answer. Long tool results are
truncated so the terminal stays readable; the size in the panel title is the
real one, which is what the context-overflow pages are about.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

console = Console()

_STYLES = {
    "human": ("👤 Human", "bold blue"),
    "ai": ("🤖 AI", "bold green"),
    "tool": ("🧰 Tool result", "bold yellow"),
    "system": ("⚙️  System", "bold magenta"),
}


def print_messages(
    messages: Any,
    *,
    skip: int = 0,
    max_chars: int = 1500,
    show_reasoning: bool = False,
    show_system: bool = False,
    show_usage: bool = True,
) -> None:
    """Print every message of an agent response (or a plain list of messages).

    Args:
        messages: the dict returned by ``agent.invoke`` / ``ainvoke``, or a list
            of messages, or a single message.
        skip: number of leading messages to skip. Handy on multi-turn threads
            with a checkpointer, where each response repeats the whole history.
        max_chars: truncate any content longer than this (the real size is
            still shown in the panel title).
        show_reasoning: print the model's reasoning / thinking blocks when the
            provider returns them (DeepSeek, Anthropic, OpenAI o-series...).
        show_system: print system messages, hidden by default.
        show_usage: print the token usage returned by the provider.
    """
    if isinstance(messages, dict) and "messages" in messages:
        messages = messages["messages"]
    if not isinstance(messages, Iterable) or isinstance(messages, (str, bytes)):
        messages = [messages]

    for message in list(messages)[skip:]:
        print_message(
            message,
            max_chars=max_chars,
            show_reasoning=show_reasoning,
            show_system=show_system,
            show_usage=show_usage,
        )


def print_message(
    message: Any,
    *,
    max_chars: int = 1500,
    show_reasoning: bool = False,
    show_system: bool = False,
    show_usage: bool = True,
) -> None:
    """Print a single LangChain message as a panel."""
    kind = getattr(message, "type", None) or "unknown"
    if kind == "system" and not show_system:
        return

    title, style = _STYLES.get(kind, (f"📨 {kind}", "bold white"))
    parts: list[Any] = []

    if kind == "ai":
        reasoning = _reasoning(message)
        if show_reasoning and reasoning:
            parts.append(Panel(_clip(reasoning, max_chars), title="💭 reasoning", style="dim", border_style="dim"))

        text = _text(message)
        if text.strip():
            parts.append(Markdown(text) if len(text) <= max_chars else _clip(text, max_chars))

        for call in getattr(message, "tool_calls", None) or []:
            parts.append(_tool_call(call, max_chars))

        usage = getattr(message, "usage_metadata", None)
        if show_usage and usage:
            title += f"  [dim]({usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out tokens)[/]"

    elif kind == "tool":
        text = _text(message)
        name = getattr(message, "name", None) or "?"
        status = getattr(message, "status", "success")
        title += f": [bold]{name}[/]  [dim]({_size(text)})[/]"
        if status == "error":
            title += "  [bold red]error[/]"
            style = "bold red"
        parts.append(_clip(text, max_chars))

    else:
        parts.append(_clip(_text(message), max_chars))

    console.print(Panel(Group(*parts) if parts else Text(""), title=title, title_align="left", border_style=style))


# --- helpers ---------------------------------------------------------------


def _text(message: Any) -> str:
    """Plain text of a message, whatever the content shape (str or blocks)."""
    text = getattr(message, "text", None)
    if not isinstance(text, str) and callable(text):  # langchain-core < 1.0 had a .text() method
        text = text()
    if isinstance(text, str) and text:
        return str(text)
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                chunks.append(block.get("text", ""))
            else:
                chunks.append(json.dumps(block, ensure_ascii=False, default=str))
        return "\n".join(chunks)
    return str(content)


def _reasoning(message: Any) -> str:
    """Reasoning / thinking text, if the provider returned any."""
    extra = getattr(message, "additional_kwargs", None) or {}
    if extra.get("reasoning_content"):  # DeepSeek
        return str(extra["reasoning_content"])
    blocks = getattr(message, "content_blocks", None) or []
    return "\n".join(
        str(b.get("reasoning") or b.get("thinking") or "")
        for b in blocks
        if isinstance(b, dict) and b.get("type") in ("reasoning", "thinking")
    )


def _tool_call(call: dict, max_chars: int) -> Panel:
    args = call.get("args") or {}
    if len(args) == 1 and isinstance(next(iter(args.values())), str):
        # Single string argument (execute's `command`, read_file's `file_path`):
        # print it raw, it reads better than JSON.
        body: Any = _clip(next(iter(args.values())), max_chars)
    else:
        rendered = json.dumps(args, indent=2, ensure_ascii=False, default=str)
        body = Syntax(rendered if len(rendered) <= max_chars else rendered[:max_chars] + "…", "json", theme="ansi_dark", word_wrap=True)
    return Panel(body, title=f"🔧 {call.get('name')}", title_align="left", border_style="cyan")


def _clip(text: str, max_chars: int) -> Text:
    if len(text) <= max_chars:
        return Text(text)
    return Text(text[:max_chars]) + Text(f"\n… [{len(text) - max_chars:,} more characters truncated]", style="dim italic")


def _size(text: str) -> str:
    return f"{len(text):,} chars ≈ {len(text) // 4:,} tokens"
