"""
test_ai.py - Sends one question to the AI and prints the reply.
Used to confirm the API key, credits, and model name all work.
"""

from openai import OpenAI

from app import config

# Create the client: the object that talks to the AI service.
# base_url=None means "use OpenAI's default address".
client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)

print(f"Sending a test question to {config.LLM_MODEL}...")

# Send the conversation and wait for the reply.
response = client.chat.completions.create(
    model=config.LLM_MODEL,
    messages=[
        {"role": "system", "content": "You are a friendly assistant. Keep answers short."},
        {"role": "user", "content": "In one sentence, what is an API?"},
    ],
)

# Dig the reply text out of the response object.
reply = response.choices[0].message.content

print("\nAI reply:", reply)
print("\nTokens used:", response.usage.total_tokens)