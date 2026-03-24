"""
Create the SQLite database schema for the AML investigation system.

Creates four tables: customers, accounts, aml_alerts_history, transactions.
Uses DROP TABLE IF EXISTS so the script is safe to re-run.
"""

import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/aml_synthetic.db")


def create_schema():
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop tables in reverse dependency order
    cursor.execute("DROP TABLE IF EXISTS transactions")
    cursor.execute("DROP TABLE IF EXISTS aml_alerts_history")
    cursor.execute("DROP TABLE IF EXISTS accounts")
    cursor.execute("DROP TABLE IF EXISTS customers")
    cursor.execute("DROP TABLE IF EXISTS watchlists")

    # Create customers table
    cursor.execute("""
        CREATE TABLE customers (
            customer_id                  TEXT PRIMARY KEY,
            full_name                    TEXT NOT NULL,
            date_of_birth                TEXT,
            nationality                  TEXT,
            country_of_residence         TEXT,
            customer_type                TEXT,
            occupation                   TEXT,
            employer_name                TEXT,
            annual_income_declared_gbp   REAL,
            source_of_funds_declared     TEXT,
            onboarding_date              TEXT,
            kyc_status                   TEXT,
            kyc_last_reviewed            TEXT,
            kyc_document_type            TEXT,
            kyc_document_expiry          TEXT,
            pep_flag                     INTEGER NOT NULL DEFAULT 0,
            sanctions_flag               INTEGER NOT NULL DEFAULT 0,
            risk_rating                  TEXT,
            address                      TEXT,
            address_country              TEXT
        )
    """)

    # Create accounts table
    cursor.execute("""
        CREATE TABLE accounts (
            account_id                   TEXT PRIMARY KEY,
            customer_id                  TEXT NOT NULL REFERENCES customers(customer_id),
            account_type                 TEXT,
            currency                     TEXT,
            account_status               TEXT,
            opening_date                 TEXT,
            last_activity_date           TEXT,
            average_monthly_balance_gbp  REAL,
            iban                         TEXT
        )
    """)

    # Create aml_alerts_history table
    cursor.execute("""
        CREATE TABLE aml_alerts_history (
            alert_id        TEXT PRIMARY KEY,
            customer_id     TEXT NOT NULL REFERENCES customers(customer_id),
            alert_date      TEXT,
            alert_type      TEXT,
            rules_triggered TEXT,
            disposition     TEXT,
            sar_filed       INTEGER NOT NULL DEFAULT 0,
            sar_reference   TEXT,
            analyst_notes   TEXT
        )
    """)

    # Create transactions table
    cursor.execute("""
        CREATE TABLE transactions (
            transaction_id                          TEXT PRIMARY KEY,
            account_id                              TEXT NOT NULL REFERENCES accounts(account_id),
            transaction_datetime                    TEXT,
            transaction_type                        TEXT,
            direction                               TEXT,
            amount_gbp                              REAL,
            original_amount                         REAL,
            original_currency                       TEXT,
            counterparty_name                       TEXT,
            counterparty_account_id                 TEXT,
            counterparty_bank_bic                   TEXT,
            counterparty_country                    TEXT,
            counterparty_is_high_risk_jurisdiction  INTEGER NOT NULL DEFAULT 0,
            payment_reference                       TEXT,
            channel                                 TEXT,
            is_international                        INTEGER NOT NULL DEFAULT 0,
            transaction_status                      TEXT
        )
    """)

    # Create watchlists table (standalone reference — no foreign keys)
    cursor.execute("""
        CREATE TABLE watchlists (
            watchlist_id              TEXT PRIMARY KEY,
            entity_name               TEXT NOT NULL,
            aliases                   TEXT,
            entity_type               TEXT,
            watchlist_type            TEXT,
            source                    TEXT,
            listed_date               TEXT,
            country_of_incorporation  TEXT,
            country_of_operation      TEXT,
            risk_score                INTEGER,
            is_absolute_prohibition   INTEGER NOT NULL DEFAULT 0,
            status                    TEXT,
            last_reviewed_date        TEXT,
            review_due_date           TEXT,
            related_entity_id         TEXT,
            notes                     TEXT
        )
    """)

    conn.commit()
    conn.close()

    print(f"Schema created successfully at: {DB_PATH}")
    print("Tables created: customers, accounts, aml_alerts_history, transactions, watchlists")


if __name__ == "__main__":
    create_schema()
