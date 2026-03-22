"""
Shared SQLite connection context manager.
All tools import get_connection from here.
Uses sqlite3.Row as row_factory so columns are accessible by name.
Loads DB_PATH from .env.
"""

import os
import sqlite3
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/aml_synthetic.db")


@contextmanager
def get_connection():
    """Yield a SQLite connection with Row factory. Closes on exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
