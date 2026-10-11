"""
check_document.py - Try the document pipeline on a real file, using the real AI.

It extracts the text, splits it into chunks, and embeds them, then prints
what happened. Nothing is saved to the database.

Run from the backend folder with:
    python check_document.py "C:\\path\\to\\your\\file.pdf"
"""

import sys
from pathlib import Path

from app.services import documents

if len(sys.argv) != 2:
    print('Usage: python check_document.py "C:\\path\\to\\file.pdf"')
    sys.exit(1)

path = Path(sys.argv[1])
if not path.is_file():
    print(f"File not found: {path}")
    sys.exit(1)

print(f"File: {path.name} ({path.stat().st_size // 1024} KB)\n")

try:
    pages = documents.extract_pages(path.name, path.read_bytes())
except documents.DocumentError as e:
    print("Problem:", e)
    sys.exit(1)

total_characters = sum(len(text) for _, text in pages)
print(f"1. Extracted text from {len(pages)} page(s): {total_characters} characters")

chunks = documents.chunk_text(pages)
print(f"2. Split into {len(chunks)} chunk(s)")

print("\n   First chunk (page {}):".format(chunks[0][0]))
print("   " + chunks[0][1][:300] + ("..." if len(chunks[0][1]) > 300 else ""))

print(f"\n3. Embedding {len(chunks)} chunk(s)... (this calls the AI)")
vectors = documents.embed_texts([text for _, text in chunks])
print(f"   Got {len(vectors)} embeddings, each with {len(vectors[0])} numbers")

print("\nThe document pipeline is working!")