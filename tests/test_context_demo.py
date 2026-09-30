"""Check the context lesson with real middleware and simulated provider failures."""

import asyncio
import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from deepagents.middleware import FilesystemMiddleware
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import ToolMessage
from openai import BadRequestError

from test_workshop import ToolCallingModel, answer


class ContextDemoTests(unittest.TestCase):
    def test_offloading_and_targeted_search(self):
        @tool
        def query() -> str:
            """Return a deliberately oversized query result."""
            return ('[1, "filler"]\n' * 10000) + '[99999, "2025-01-21", "Lyon", "webcam", 47.24]\n'

        model = ToolCallingModel(responses=[
            answer("", tool_calls=[{"name": "query", "args": {}, "id": "large"}]),
            answer("", tool_calls=[{
                "name": "grep", "args": {"pattern": "[99999,", "path": "/", "output_mode": "content"}, "id": "lookup",
            }]),
            answer("Found order 99999"),
        ])
        agent = create_agent(model=model, tools=[query], middleware=[FilesystemMiddleware()])
        result = asyncio.run(agent.ainvoke({"messages": [("user", "Find order 99999")]}))
        tool_results = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual(len(tool_results), 2)
        self.assertTrue(result["files"], "The large payload should be stored outside model context")
        self.assertLess(len(tool_results[0].content), 5000)
        self.assertEqual(tool_results[1].status, "success")
        self.assertIn('[99999, "2025-01-21", "Lyon", "webcam", 47.24]', tool_results[1].content)
        self.assertLess(len(tool_results[1].content), 1000)

    def test_page_five_classifies_only_context_rejections(self):
        path = Path(__file__).resolve().parents[1] / "solutions/05_react_agent_context_overflow.py"
        spec = importlib.util.spec_from_file_location("context_demo", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        response = httpx.Response(400, request=httpx.Request("POST", "https://example.invalid"))
        cases = [
            (BadRequestError("too long", response=response, body={"code": "context_length_exceeded"}), True),
            (BadRequestError("maximum context length exceeded", response=response, body={}), True),
            (BadRequestError("invalid model", response=response, body={"code": "invalid_model"}), False),
            (ConnectionError("MCP unavailable"), False),
        ]
        for error, expected in cases:
            with self.subTest(error=str(error)):
                adapter = AsyncMock()
                adapter.__aenter__.return_value = adapter
                adapter.list_tools.return_value = []
                agent = AsyncMock()
                agent.ainvoke.side_effect = error
                output = io.StringIO()
                with (
                    patch.object(module, "ChatOpenAI"),
                    patch.object(module, "MCPAdapter", return_value=adapter),
                    patch.object(module, "create_agent", return_value=agent),
                    redirect_stdout(output),
                ):
                    if expected:
                        asyncio.run(module.main())
                        self.assertIn("Expected context-limit rejection", output.getvalue())
                    else:
                        with self.assertRaises(type(error)):
                            asyncio.run(module.main())
                        self.assertNotIn("Expected context-limit rejection", output.getvalue())


if __name__ == "__main__":
    unittest.main()
