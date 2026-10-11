"""
check_embeddings.py - See embeddings in action, before building RAG.

It turns a few sentences into embeddings (lists of numbers), then measures
how similar each sentence is to a question. Sentences with similar MEANING
score higher, even when they share no words with the question.

Run from the backend folder with:  python check_embeddings.py
"""

import math

from openai import OpenAI

from app import config

client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def embed(texts: list[str]) -> list[list[float]]:
    """Turn each text into an embedding (a list of numbers)."""
    response = client.embeddings.create(model=config.EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """How similar two embeddings are: 1.0 = same meaning, near 0 = unrelated."""
    dot = sum(x * y for x, y in zip(a, b))
    length_a = math.sqrt(sum(x * x for x in a))
    length_b = math.sqrt(sum(y * y for y in b))
    return dot / (length_a * length_b)


sentences = [
    "Kruthi built a chatbot using Python and FastAPI.",
    "The weather in Bengaluru is pleasant in December.",
    "She knows backend web development and REST APIs.",
    "Masala dosa is a popular South Indian breakfast.",
]
question = "What programming skills does Kruthi have?"

print(f"Embedding model: {config.EMBEDDING_MODEL}\n")

vectors = embed(sentences + [question])
sentence_vectors, question_vector = vectors[:-1], vectors[-1]

print(f"Each embedding is a list of {len(question_vector)} numbers.")
print("First 5 numbers of the question's embedding:")
print("  ", [round(n, 4) for n in question_vector[:5]], "\n")

print(f'Question: "{question}"\n')
print("Similarity to each sentence (higher = more related):")

scored = [
    (cosine_similarity(question_vector, vector), sentence)
    for sentence, vector in zip(sentences, sentence_vectors)
]
for score, sentence in sorted(scored, reverse=True):
    print(f"  {score:.3f}  {sentence}")

print("\nEmbeddings are working!")