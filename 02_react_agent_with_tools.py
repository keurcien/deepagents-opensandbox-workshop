import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool

model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))


@tool
def greet(name: str):
    """Greet someone with his name."""
    return f"Hi {name}"

@tool
def add(x: int, y: int):
    """Return the result of x + y."""
    return x + y


agent = create_agent(model=model, tools=[greet, add])

#first_response = agent.invoke({"messages": [{"role": "user", "content": "hi, my name is Philippe"}]})

#rint(first_response)

second_response = agent.invoke({"messages": [{"role": "user", "content": "how much is 1 + 10"}]})

print(second_response)