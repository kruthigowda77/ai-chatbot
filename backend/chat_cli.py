"""
chat_cli.py - A simple chatbot that runs in the terminal.
Demonstrates how conversation memory works: we keep a list of
messages and send the WHOLE list to the AI every time.
"""

from openai import OpenAI

from app import config

client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)

# The conversation history. It starts with just the system instructions.
messages = [
    {"role": "system", "content": "You are a helpful, friendly assistant."}
]

print("Chatbot ready! Type your message, or 'quit' to exit.\n")

while True:
    user_input = input("You: ").strip()

    if user_input.lower() in ("quit", "exit"):
        print("Goodbye!")
        break
    if not user_input:
        continue  # ignore empty input

    # 1. Add the user's message to the history.
    messages.append({"role": "user", "content": user_input})

    # 2. Send the ENTIRE history to the AI.
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
    )
    reply = response.choices[0].message.content

    # 3. Add the AI's reply to the history, so it "remembers" next time.
    messages.append({"role": "assistant", "content": reply})

    print(f"\nBot: {reply}\n")
    print(f"(Messages in history: {len(messages)})\n")