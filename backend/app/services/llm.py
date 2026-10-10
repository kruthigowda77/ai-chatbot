"""
llm.py - Everything related to talking to the AI model.

Other parts of the app call get_ai_reply() and don't need to know
which AI provider or library is used underneath.
"""

import logging

import openai
from openai import OpenAI

from app import config

logger = logging.getLogger(__name__)

# Create ONE client when the app starts and reuse it for every request.
client = OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=config.LLM_BASE_URL,
    timeout=30.0,     # give up on a single attempt after 30 seconds
    max_retries=2,    # automatically retry temporary failures twice
)

# Instructions that shape the bot's personality and behavior.
SYSTEM_PROMPT = (
    "You are a helpful, friendly AI assistant. "
    "Give clear, accurate answers. Keep responses concise unless "
    "the user asks for more detail."
)

# Shown to users when the problem is on our side (key, model name).
CONFIG_PROBLEM_MESSAGE = (
    "The chatbot isn't configured correctly right now. Please contact the site owner."
)


class LLMServiceError(Exception):
    """
    Raised when the AI service fails.
    Carries a user-friendly message and the HTTP status code to return.
    """

    def __init__(self, user_message: str, status_code: int = 503):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


def get_ai_reply(messages: list[dict]) -> str:
    """
    Send a list of chat messages to the AI and return its reply text.
    Raises LLMServiceError with a friendly message if anything goes wrong.
    """
    full_conversation = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    try:
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=full_conversation,
        )

    # Order matters: APITimeoutError is a special kind of APIConnectionError,
    # so it must be checked first.
    except openai.APITimeoutError as e:
        logger.warning("AI request timed out: %s", e)
        raise LLMServiceError(
            "The AI took too long to respond. Please try again.", 504
        ) from e

    except openai.APIConnectionError as e:
        logger.warning("Could not connect to the AI service: %s", e)
        raise LLMServiceError(
            "Couldn't reach the AI service. Please check the internet connection and try again.", 503
        ) from e

    except openai.RateLimitError as e:
        logger.warning("Rate limit reached: %s", e)
        raise LLMServiceError(
            "Too many requests right now. Please wait a moment and try again.", 429
        ) from e

    except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
        logger.error("AI authentication failed - check LLM_API_KEY in .env: %s", e)
        raise LLMServiceError(CONFIG_PROBLEM_MESSAGE, 500) from e

    except openai.NotFoundError as e:
        logger.error("AI model not found - check LLM_MODEL in .env (currently '%s'): %s",
                     config.LLM_MODEL, e)
        raise LLMServiceError(CONFIG_PROBLEM_MESSAGE, 500) from e

    except openai.BadRequestError as e:
        logger.warning("AI rejected the request: %s", e)
        raise LLMServiceError(
            "The AI couldn't process that message. Please try rephrasing it.", 400
        ) from e

    except openai.InternalServerError as e:
        logger.warning("AI service is overloaded or failing: %s", e)
        raise LLMServiceError(
            "The AI service is busy right now. Please try again in a moment.", 503
        ) from e

    except openai.APIError as e:
        # Any other error from the AI library we didn't list above.
        logger.error("Unexpected AI service error: %s", e)
        raise LLMServiceError(
            "Something went wrong with the AI service. Please try again.", 502
        ) from e

    reply = response.choices[0].message.content
    if not reply:
        logger.warning("AI returned an empty reply")
        raise LLMServiceError(
            "The AI returned an empty response. Please try rephrasing your message.", 502
        )

    return reply