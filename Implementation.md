# AML Investigator – Implementation Details

The investigator evaluates suspicious-activity alerts, gathers evidence from a
local SQLite database, and streams its findings and final verdict to a dashboard.
SAR recommendations and duplicate-filing checks are part of the verdict. Report
drafting and configuration editors are excluded from this branch.

## Investigation flow

1. The dashboard loads synthetic alerts through `GET /api/alerts`.
2. `POST /investigate` accepts an `AlertPayload` and builds a system prompt from
   the triggered AML rules and evidence guidelines in `config/aml_rules.json`.
3. The LangGraph agent in `agent/graph.py` alternates between model responses and
   evidence tool calls until it produces a verdict.
4. Server-sent events carry investigation text, tool calls, evidence results,
   errors, and the final verdict to the dashboard.
5. The evidence drawer retrieves source database records through `/data/...`
   endpoints so an analyst can verify the findings.

The command-line entry point, `run_investigation.py`, uses the same graph and
prompts through `agent/runner.py`.

## Evidence tools

- `get_customer_profile`: customer identity, KYC, income, PEP and sanctions flags.
- `get_account_summary`: account identifiers, statuses and dormancy signals.
- `get_transaction_history`: transaction samples, totals and behavioural signals.
- `get_prior_alert_history`: previous alerts, SAR filings and duplicate checks.
- `screen_watchlist`: matching watchlist entries and supporting records.

All tools use the SQLite connection manager in `tools/db.py`. The CSV fixtures
and scripts in `data/` recreate the synthetic demo database.

## Models and configuration

`agent/llm.py` selects the provider and model from `.env`. The default Codex
adapter starts a local app-server process, uses the existing ChatGPT login, and
streams public response text. Structured application tool requests execute through
LangGraph after validation. Other supported providers use their configured keys.

Edit `config/aml_rules.json` to change the AML definitions and evidence guidelines,
then restart the server. See `README.md` for setup and launch instructions.

## Verification

Run `venv/bin/python -m pytest tests -q` after initializing the sample database.
The suite covers evidence tools, Codex transport and streaming with stubs, and
investigator API routes. It does not make live model requests.
