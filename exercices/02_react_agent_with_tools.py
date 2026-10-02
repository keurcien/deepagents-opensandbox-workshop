"""Page 2: give the agent tools.

Goal: declare two Python functions as tools and let the agent call them.
The docstring of a tool is what the model reads to decide when to use it.

Run:
    uv run --env-file .env python exercices/02_react_agent_with_tools.py

Success: The trace contains an add call with 1 and 10, returning 11.

Challenge: Ask the agent to greet you and add two numbers in the same request.
"""

import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

# TODO 1: turn this function into a tool with the `@tool` decorator and give it
#         a one-line docstring describing what it does.
def greet(name: str):
    return f"Hi {name}, welcome to Volcamp"

# TODO 2: write a second tool `add(x: int, y: int)` that returns x + y.
...

# TODO 3: pass both tools to the agent.
agent = create_agent(model=model, tools=...)

with LiveProgress() as progress:
    response = agent.invoke({"messages": [{"role": "user", "content": "Use the add tool to calculate 1 + 10"}]}, config={"callbacks": [progress]})

# Look at the trace: an AI message with a tool call, a tool result, then the answer.
print_messages(response)
