# AML SAR Investigator

A LangGraph-based AI agent that investigates suspicious customer activity and determines whether alerts are true positives or false positives.

## Tech Stack

- **LLM:** `llama-3.3-70b-versatile` via Groq API
- **Agent Framework:** LangGraph with LangChain
- **Database:** SQLite (seeded from CSV files)
- **Validation:** Pydantic schemas

## Project Structure

```
├── data/                          # Database and CSV data
│   ├── csv/                       # Source CSV files
│   └── scripts/                   # Schema creation and seeding
├── tools/                         # LangChain tool definitions
│   └── internal/                  # Four investigation tools
├── agent/                         # LangGraph agent (state, graph, prompts, runner)
├── schemas/                       # Pydantic models (AlertPayload, InvestigationVerdict)
└── tests/                         # Tool tests and sample alerts
```

## Setup & Run

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate.fish       # fish shell
# source venv/bin/activate          # bash/zsh

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 4. Create database schema
python data/scripts/create_schema.py

# 5. Seed database from CSVs
python data/scripts/seed_database.py

# 6. Run tool tests (must pass before running the agent)
python -m pytest tests/test_tools.py -v

# 7. Run an investigation
python run_investigation.py tests/sample_alerts/true_positive.json
python run_investigation.py tests/sample_alerts/false_positive.json
```

## Investigation Tools

| Tool | Purpose |
|------|---------|
| `get_customer_profile` | KYC profile with PEP/sanctions/income flags |
| `get_account_summary` | All accounts with dormancy detection |
| `get_transaction_history` | Transactions with AML signal flags |
| `get_prior_alert_history` | Previous alerts with SAR duplicate check |

## AML Rules Covered

- **RULE-01** — Structuring / Smurfing
- **RULE-02** — Rapid Movement of Funds
- **RULE-03** — High-Risk Jurisdiction Transfer
- **RULE-04** — Transaction-Profile Mismatch
- **RULE-05** — Dormant Account Reactivation
- **RULE-06** — Third-Party Funding
- **RULE-07** — PEP / Sanctions Proximity
- **RULE-08** — Round Tripping / Layering
