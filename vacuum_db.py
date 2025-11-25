#!/usr/bin/env python3
"""Vacuum the SQLite database to improve performance."""

from backend.database.database import engine
from sqlalchemy import text

def vacuum_db():
    # SQLite VACUUM must be executed on a separate connection
    with engine.connect() as conn:
        conn.execute(text("VACUUM"))
        print("✅ Database vacuum completed.")

if __name__ == "__main__":
    vacuum_db()
