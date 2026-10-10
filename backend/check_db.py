"""
check_db.py - Saves a test conversation, reads it back, then deletes it.
Run from the backend folder with:  python check_db.py
"""

from sqlalchemy import func, select

from app import config
from app.db.database import SessionLocal, init_db
from app.db.models import Conversation, Message

print("Database:", config.DATABASE_URL)
init_db()

# 1. CREATE: save a conversation with two messages
with SessionLocal() as db:
    convo = Conversation(title="Test chat")
    convo.messages.append(Message(role="user", content="My name is Kruthi"))
    convo.messages.append(Message(role="assistant", content="Nice to meet you, Kruthi!"))

    db.add(convo)
    db.commit()  # save to the database
    convo_id = convo.id
    print(f"\n1. Saved conversation {convo_id}")

# 2. READ: load it back in a brand-new session (proves it was really saved)
with SessionLocal() as db:
    saved = db.get(Conversation, convo_id)
    print(f"2. Loaded '{saved.title}' with {len(saved.messages)} messages:")
    for msg in saved.messages:
        print(f"     [{msg.role}] {msg.content}")

    # 3. DELETE: remove it (its messages are deleted too, thanks to cascade)
    db.delete(saved)
    db.commit()

# 4. CHECK: confirm no messages were left behind
with SessionLocal() as db:
    remaining = db.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == convo_id)
    )
    print(f"3. Deleted. Messages left for that conversation: {remaining}")

print("\nDatabase is working!")