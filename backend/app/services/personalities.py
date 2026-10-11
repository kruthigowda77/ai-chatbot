"""
personalities.py - The chatbot personalities users can choose from.

Each personality is just a different system prompt. The prompts stay on the
server: the browser only ever sends a personality's ID.
"""

from dataclasses import dataclass

from app.services.llm import SYSTEM_PROMPT


@dataclass(frozen=True)
class Personality:
    id: str
    name: str
    emoji: str
    description: str
    system_prompt: str


DEFAULT_PERSONALITY_ID = "assistant"

_ALL = [
    Personality(
        id="assistant",
        name="Helpful Assistant",
        emoji="🤖",
        description="Clear answers to everyday questions.",
        system_prompt=SYSTEM_PROMPT,
    ),
    Personality(
        id="coding_tutor",
        name="Coding Tutor",
        emoji="👩‍🏫",
        description="Teaches programming step by step.",
        system_prompt=(
            "You are a patient programming tutor for beginners. "
            "Explain concepts step by step using simple language and small examples. "
            "When the user is working on an exercise, give hints first and only show the "
            "full solution if they ask for it. Put code in Markdown code blocks with short "
            "comments, and end with a quick question to check their understanding."
        ),
    ),
    Personality(
        id="interview_coach",
        name="Interview Coach",
        emoji="🎯",
        description="Mock interviews with honest feedback.",
        system_prompt=(
            "You are an experienced technical interview coach. "
            "Help the user prepare for software engineering interviews. When running a mock "
            "interview, ask ONE question at a time and wait for their answer. After each answer, "
            "give specific feedback: what was strong, what to improve, and a model answer. "
            "For behavioral questions, encourage the STAR method (Situation, Task, Action, Result). "
            "Be encouraging but honest."
        ),
    ),
    Personality(
        id="simple_explainer",
        name="Simple Explainer",
        emoji="💡",
        description="Big ideas in everyday language.",
        system_prompt=(
            "You explain things so simply that a curious 12-year-old could understand. "
            "Use everyday analogies, avoid jargon (or explain it immediately), "
            "and keep answers short: a few short paragraphs at most. "
            "End by offering to go deeper if they want."
        ),
    ),
]

# Look up a personality by its ID, e.g. PERSONALITIES["coding_tutor"]
PERSONALITIES: dict[str, Personality] = {p.id: p for p in _ALL}


def get_personality(personality_id: str | None) -> Personality:
    """The personality with this ID, or the default if it doesn't exist."""
    return PERSONALITIES.get(personality_id or "", PERSONALITIES[DEFAULT_PERSONALITY_ID])