"""Check the context lesson with real middleware."""

import asyncio
import unittest

from deepagents.middleware import FilesystemMiddleware
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import ToolMessage

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

if __name__ == "__main__":
    unittest.main()
