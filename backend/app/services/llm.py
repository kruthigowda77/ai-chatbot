"""
llm.py - Everything related to talking to the AI model.

Other parts of the app call get_ai_reply() or stream_ai_reply() and
don't need to know which AI provider or library is used underneath.
"""

import logging
from collections.abc import Iterator

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

# The default instructions (used by the "Helpful Assistant" personality).
SYSTEM_PROMPT = (
    "You are a helpful, friendly AI assistant. "
    "Give clear, accurate answers. Keep responses concise unless "
    "the user asks for more detail."
)

# Shown to users when the problem is on our side (key, model name).
CONFIG_PROBLEM_MESSAGE = (
    "The chatbot isn't configured correctly right now. Please contact the site owner."
)

# Added to the end of a reply if the stream breaks partway through.
STREAM_INTERRUPTED_MESSAGE = "\n\n[The response was interrupted. Please try again.]"


class LLMServiceError(Exception):
    """
    Raised when the AI service fails.
    Carries a user-friendly message and the HTTP status code to return.
    """

    def __init__(self, user_message: str, status_code: int = 503):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


def _with_system_prompt(messages: list[dict], system_prompt: str) -> list[dict]:
    """Put the system prompt in front of the conversation."""
    return [dict(role="system", content=system_prompt)] + messages


def _translate_error(e: openai.APIError) -> LLMServiceError:
    """
    Convert an error from the AI library into our own LLMServiceError,
    logging the technical details for developers.
    """
    # Order matters: APITimeoutError is a special kind of APIConnectionError.
    if isinstance(e, openai.APITimeoutError):
        logger.warning("AI request timed out: %s", e)
        return LLMServiceError("The AI took too long to respond. Please try again.", 504)

    if isinstance(e, openai.APIConnectionError):
        logger.warning("Could not connect to the AI service: %s", e)
        return LLMServiceError(
            "Couldn't reach the AI service. Please check the internet connection and try again.", 503
        )

    if isinstance(e, openai.RateLimitError):
        logger.warning("Rate limit reached: %s", e)
        return LLMServiceError("Too many requests right now. Please wait a moment and try again.", 429)

    if isinstance(e, (openai.AuthenticationError, openai.PermissionDeniedError)):
        logger.error("AI authentication failed - check LLM_API_KEY in .env: %s", e)
        return LLMServiceError(CONFIG_PROBLEM_MESSAGE, 500)

    if isinstance(e, openai.NotFoundError):
        logger.error("AI model not found - check LLM_MODEL in .env (currently '%s'): %s",
                     config.LLM_MODEL, e)
        return LLMServiceError(CONFIG_PROBLEM_MESSAGE, 500)

    if isinstance(e, openai.BadRequestError):
        logger.warning("AI rejected the request: %s", e)
        return LLMServiceError("The AI couldn't process that message. Please try rephrasing it.", 400)

    if isinstance(e, openai.InternalServerError):
        logger.warning("AI service is overloaded or failing: %s", e)
        return LLMServiceError("The AI service is busy right now. Please try again in a moment.", 503)

    logger.error("Unexpected AI service error: %s", e)
    return LLMServiceError("Something went wrong with the AI service. Please try again.", 502)


def get_ai_reply(messages: list[dict], system_prompt: str = SYSTEM_PROMPT) -> str:
    """
    Send the conversation to the AI and return the complete reply text.
    Raises LLMServiceError with a friendly message if anything goes wrong.
    """
    try:
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=_with_system_prompt(messages, system_prompt),
        )
    except openai.APIError as e:
        raise _translate_error(e) from e

    reply = response.choices[0].message.content
    if not reply:
        logger.warning("AI returned an empty reply")
        raise LLMServiceError(
            "The AI returned an empty response. Please try rephrasing your message.", 502
        )
    return reply


def stream_ai_reply(messages: list[dict], system_prompt: str = SYSTEM_PROMPT) -> Iterator[str]:
    """
    Send the conversation to the AI and return a generator that yields
    the reply in small text pieces as they arrive.

    Errors while STARTING the request raise LLMServiceError immediately,
    so the API can still send a proper error response.
    """
    try:
        stream = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=_with_system_prompt(messages, system_prompt),
            stream=True,  # ask the AI to send the reply in pieces
        )
    except openai.APIError as e:
        raise _translate_error(e) from e

    def generate() -> Iterator[str]:
        try:
            for chunk in stream:
                # Each chunk holds a small piece of text (or sometimes nothing)
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except openai.APIError as e:
            # The reply already started, so we can't send an error status anymore.
            # Instead, add a short note to the end of the text.
            logger.warning("Stream interrupted: %s", e)
            yield STREAM_INTERRUPTED_MESSAGE

    return generate()