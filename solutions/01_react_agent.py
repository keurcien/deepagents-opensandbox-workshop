import os
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from volcamp.pretty import print_messages
from volcamp.progress import LiveProgress

model = ChatOpenAI(model="deepseek-flash", base_url="https://api.deepseek.com", api_key=os.getenv("DEEPSEEK_API_KEY"))

agent = create_agent(model=model)

with LiveProgress() as progress:
    response = agent.invoke({"messages": [{"role": "user", "content": "hi"}]}, config={"callbacks": [progress]})

print_messages(response)
