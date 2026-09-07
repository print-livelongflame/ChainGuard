from openai import OpenAI
from api_keys.api_keys import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def ask_llm(prompt: str) -> str:
    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text

userin = input("Enter your prompt: ")
print(ask_llm(userin))