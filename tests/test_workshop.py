"""Offline integration checks: real agent loops, fake model responses, no API calls."""

import asyncio
import csv
import io
import unittest
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langgraph.checkpoint.memory import InMemorySaver
from rich.console import Console

from volcamp.progress import LiveProgress


class ToolCallingModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def answer(content, *, tool_calls=None):
    return AIMessage(
        content=content,
        tool_calls=tool_calls or [],
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.progress = LiveProgress(Console(file=self.output, width=500, color_system=None))

    def make_agent(self):
        @tool
        def add(x: int, y: int) -> int:
            """Add two integers."""
            # The event must already be visible while the tool is still running.
            self.assertIn("Tool add started", self.output.getvalue())
            return x + y

        model = ToolCallingModel(responses=[
            answer("", tool_calls=[{"name": "add", "args": {"x": 1, "y": 10}, "id": "sum"}]),
            answer("11"),
        ])
        return create_agent(model=model, tools=[add])

    def assert_summary(self, result):
        self.assertEqual(result["messages"][-1].content, "11")
        trace = self.output.getvalue()
        self.assertIn("Tool add completed", trace)
        self.assertIn("2 model calls, 1 tool calls", trace)
        self.assertIn("20 input / 10 output tokens", trace)
        self.assertIn("usage reported for 2/2 calls", trace)
        self.assertEqual(self.progress.tool_calls, 1)

    def test_sync_tool_loop(self):
        agent = self.make_agent()
        with self.progress:
            result = agent.invoke({"messages": [("user", "Add 1 and 10")]}, config={"callbacks": [self.progress]})
        self.assert_summary(result)

    def test_async_tool_loop(self):
        agent = self.make_agent()

        async def run():
            with self.progress:
                return await agent.ainvoke({"messages": [("user", "Add 1 and 10")]}, config={"callbacks": [self.progress]})

        self.assert_summary(asyncio.run(run()))

    def test_failure_keeps_tool_trace_and_propagates(self):
        @tool
        def fail() -> str:
            """Simulate a broken service."""
            raise RuntimeError("service unavailable")

        model = ToolCallingModel(responses=[
            answer("", tool_calls=[{"name": "fail", "args": {}, "id": "failure"}]),
        ])
        agent = create_agent(model=model, tools=[fail])
        with self.assertRaisesRegex(RuntimeError, "service unavailable"):
            with self.progress:
                agent.invoke({"messages": [("user", "Try the service")]}, config={"callbacks": [self.progress]})
        trace = self.output.getvalue()
        self.assertIn("Tool fail started", trace)
        self.assertIn("Tool fail failed: RuntimeError", trace)
        self.assertIn("Agent failed", trace)

    def test_missing_usage_is_explicit(self):
        agent = create_agent(model=ToolCallingModel(responses=[AIMessage(content="hi")]))
        with self.progress:
            agent.invoke({"messages": [("user", "hi")]}, config={"callbacks": [self.progress]})
        self.assertIn("token usage unavailable", self.output.getvalue())
        self.assertIn("usage reported for 0/1 calls", self.output.getvalue())

    def test_provider_usage_is_not_double_counted(self):
        # Some providers supply usage in both places on the same result.
        self.progress.on_llm_end(LLMResult(
            generations=[[ChatGeneration(message=answer("hi"))]],
            llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
        ))
        self.assertEqual((self.progress.input_tokens, self.progress.output_tokens), (10, 5))
        self.assertEqual(self.progress.calls_with_usage, 1)

    def test_provider_usage_fallback(self):
        self.progress.on_llm_end(LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="hi"))]],
            llm_output={"token_usage": {"prompt_tokens": 12, "completion_tokens": 3}},
        ))
        self.assertEqual((self.progress.input_tokens, self.progress.output_tokens), (12, 3))
        self.assertEqual(self.progress.calls_with_usage, 1)

    def test_large_result_preview_is_bounded(self):
        self.progress.on_tool_start({"name": "query"}, "SELECT *", run_id="query")
        self.progress.on_tool_end("x" * 1_000_000, run_id="query")
        trace = self.output.getvalue()
        self.assertIn("1,000,000 chars", trace)
        self.assertLess(len(trace), 500)

    def test_progress_does_not_break_thread_memory(self):
        agent = create_agent(
            model=ToolCallingModel(responses=[answer("one"), answer("two")]),
            checkpointer=InMemorySaver(),
        )
        for question in ("first", "second"):
            with LiveProgress(Console(file=self.output)) as progress:
                result = agent.invoke(
                    {"messages": [("user", question)]},
                    config={"configurable": {"thread_id": "same"}, "callbacks": [progress]},
                )
                self.assertEqual(progress.model_calls, 1)
        self.assertEqual([m.content for m in result["messages"]], ["first", "one", "second", "two"])
        with self.progress:
            fresh = agent.invoke(
                {"messages": [("user", "new")]},
                config={"configurable": {"thread_id": "different"}, "callbacks": [self.progress]},
            )
        self.assertEqual(len(fresh["messages"]), 2)


class ReferenceDataTests(unittest.TestCase):
    def test_documented_answers(self):
        path = Path(__file__).resolve().parents[1] / "volcamp/mcp/orders.csv"
        with path.open(newline="") as source:
            rows = list(csv.DictReader(source))
        totals = defaultdict(Decimal)
        for row in rows:
            totals[row["city"]] += Decimal(row["amount"])
        self.assertEqual(len(rows), 100_000)
        self.assertEqual(sum(totals.values()), Decimal("32898506.88"))
        self.assertEqual(max(totals.items(), key=lambda pair: pair[1]), ("Paris", Decimal("13986204.84")))
        self.assertEqual(next(row for row in rows if row["id"] == "99999"), {
            "id": "99999", "date": "2025-01-21", "city": "Lyon", "product": "webcam", "amount": "47.24",
        })


if __name__ == "__main__":
    unittest.main()
