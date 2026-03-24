"""
Seed the SQLite database from CSV files.

Reads customers.csv, accounts.csv, aml_alerts_history.csv, and transactions.csv
from data/csv/ and inserts rows into the corresponding tables.

Uses csv.DictReader (no pandas). Applies type coercion for booleans, numerics,
and empty strings. Uses INSERT OR IGNORE so re-running is safe.
"""

import csv
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/aml_synthetic.db")

# Project root is two levels up from this script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CSV_DIR = os.path.join(PROJECT_ROOT, "data", "csv")

# Columns that should be coerced to integer (0/1) from boolean strings
BOOLEAN_COLUMNS = {
    "pep_flag",
    "sanctions_flag",
    "counterparty_is_high_risk_jurisdiction",
    "is_international",
    "sar_filed",
    "is_absolute_prohibition",
}

# Columns that should be coerced to float
NUMERIC_COLUMNS = {
    "annual_income_declared_gbp",
    "average_monthly_balance_gbp",
    "amount_gbp",
    "original_amount",
}

# Columns that should be coerced to integer
INTEGER_COLUMNS = {
    "risk_score",
}


def coerce_boolean(value: str):
    """Convert boolean string to integer 0/1 or None."""
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("true", "1"):
        return 1
    if v in ("false", "0"):
        return 0
    if v == "":
        return None
    return None


def coerce_numeric(value: str):
    """Convert numeric string to float or None."""
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def coerce_string(value: str):
    """Strip whitespace; empty string becomes None."""
    if value is None:
        return None
    v = value.strip()
    return v if v != "" else None


def coerce_integer(value: str):
    """Convert numeric string to integer or None."""
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def coerce_row(row: dict) -> dict:
    """Apply type coercion to a single row dict."""
    result = {}
    for key, value in row.items():
        if key in BOOLEAN_COLUMNS:
            result[key] = coerce_boolean(value)
        elif key in INTEGER_COLUMNS:
            result[key] = coerce_integer(value)
        elif key in NUMERIC_COLUMNS:
            result[key] = coerce_numeric(value)
        elif key == "rules_triggered":
            # Store as-is (pipe-separated string)
            result[key] = coerce_string(value)
        else:
            result[key] = coerce_string(value)
    return result


def load_table(conn: sqlite3.Connection, table_name: str, csv_filename: str):
    """Load a single CSV file into the specified table."""
    csv_path = os.path.join(CSV_DIR, csv_filename)

    if not os.path.exists(csv_path):
        print(f"WARNING: {csv_path} not found — skipping {table_name}")
        return

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [coerce_row(row) for row in reader]

    if not rows:
        print(f"WARNING: {csv_filename} is empty — skipping {table_name}")
        return

    columns = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    sql = f"INSERT OR IGNORE INTO {table_name} ({col_names}) VALUES ({placeholders})"

    values = [tuple(row[col] for col in columns) for row in rows]
    conn.executemany(sql, values)
    conn.commit()

    # Verify row count
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name}: {count} rows loaded")


def seed_database():
    """Seed all tables from CSV files."""
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}. Run create_schema.py first.")
        return

    conn = sqlite3.connect(DB_PATH)

    print("Seeding database...")

    # Load in dependency order
    load_table(conn, "customers", "customers.csv")
    load_table(conn, "accounts", "accounts.csv")
    load_table(conn, "aml_alerts_history", "aml_alerts_history.csv")
    load_table(conn, "transactions", "transactions.csv")
    load_table(conn, "watchlists", "watchlists.csv")

    conn.close()
    print("Seeding complete.")


if __name__ == "__main__":
    seed_database()
