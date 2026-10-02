import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

@tool
def greet(name: str):
    """Greet someone with his name."""
    return f"Hi {name}, welcome to Volcamp"

@tool
def add(x: int, y: int):
    """Return the result of x + y."""
    return x + y

agent = create_agent(model=model, tools=[greet, add])

with LiveProgress() as progress:
    response = agent.invoke({"messages": [{"role": "user", "content": "Use the add tool to calculate 1 + 10"}]}, config={"callbacks": [progress]})

print_messages(response)
