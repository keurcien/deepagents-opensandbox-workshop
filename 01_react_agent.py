import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

agent = create_agent(model=model)

response = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})

print(response)