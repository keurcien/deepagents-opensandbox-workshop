"""Page 1: the smallest possible agent.

Goal: build a react agent with `create_agent`, send it one message and print
the conversation with `print_messages`.

Run:
    uv run --env-file .env python exercices/01_react_agent.py
"""

import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from volcamp.pretty import print_messages

model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

# TODO 1: create the agent from the model (no tools yet).
agent = ...

# TODO 2: invoke it with a single user message saying "hi".
#         The input is a dict with a "messages" list of {"role": ..., "content": ...}.
response = ...

print_messages(response)
