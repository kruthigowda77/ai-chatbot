"""
migrate_add_personality.py - Adds the 'personality' column to existing databases.

A migration changes a database's structure WITHOUT deleting its data.
This one is safe to run more than once: it skips the change if already done.

Run from the backend folder with:  python migrate_add_personality.py
"""

from sqlalchemy import inspect, text

from app.db.database import engine

inspector = inspect(engine)

if not inspector.has_table("conversations"):
    print("No database yet - nothing to migrate. It will be created with the new column.")
else:
    columns = [column["name"] for column in inspector.get_columns("conversations")]

    if "personality" in columns:
        print("Already up to date: 'personality' column exists.")
    else:
        with engine.begin() as connection:  # begin() = one transaction, committed at the end
            connection.execute(text(
                "ALTER TABLE conversations "
                "ADD COLUMN personality VARCHAR(30) NOT NULL DEFAULT 'assistant'"
            ))
        print("Done: added 'personality' column. Existing chats use 'assistant'.")
        