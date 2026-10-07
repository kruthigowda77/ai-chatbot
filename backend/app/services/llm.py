"""
llm.py - Everything related to talking to the AI model.

Other parts of the app call get_ai_reply() and don't need to know
which AI provider or library is used underneath.
"""

from openai import OpenAI

from app import config

# Create ONE client when the app starts and reuse it for every request.
# Creating a new client per request would be slower.
client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)

# Instructions that shape the bot's personality and behavior.
SYSTEM_PROMPT = (
    "You are a helpful, friendly AI assistant. "
    "Give clear, accurate answers. Keep responses concise unless "
    "the user asks for more detail."
)


def get_ai_reply(messages: list[dict]) -> str:
    """
    Send a list of chat messages to the AI and return its reply text.

    `messages` is a list like:
        [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}, ...]
    The system prompt is added automatically at the start.
    """
    full_conversation = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=full_conversation,
    )

    return response.choices[0].message.content