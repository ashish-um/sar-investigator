# AML SAR Investigator

A local web dashboard and LangGraph agent for investigating suspicious-activity
alerts, gathering evidence from SQLite, and drafting SAR sections. The repository
includes synthetic customer, account, transaction, alert, and watchlist fixtures.

The default configuration uses **GPT-6 Luna through a ChatGPT-authenticated Codex
CLI**. Generated text streams into the investigation dashboard and SAR editor.
Other supported model providers can be selected in `.env`.

## Set up on a new Windows laptop

### 1. Install prerequisites and get the code

- **Python 3.13**, the version used to verify this project, available as `python`.
- A current native [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) with
  `app-server` support, available as `codex`.
- **Git** if cloning the repository, or a copy of the updated project folder.
- Internet access for Codex inference and the frontend's Tailwind/font CDNs.

Clone the repository, replacing `REPOSITORY_URL` with its actual Git URL:

```powershell
git clone REPOSITORY_URL sar-investigator
cd sar-investigator
```

Run the following commands from the project root. The paths below use the virtual
environment's Python directly, so PowerShell environment activation is optional.

### 2. Sign in to Codex with ChatGPT

```powershell
codex --version
codex login
codex login status
```

Complete the browser sign-in with the ChatGPT account you want to use. Status must
report `Logged in using ChatGPT`. Run the web server as the same OS user and in the
same environment as that login. See the [official authentication guide](https://learn.chatgpt.com/docs/auth).

The Codex provider needs no OpenAI API key. Account/model access and subscription
usage limits apply. The adapter rejects API-key logins. Sign in again on the new
laptop; the project does not contain or transfer your Codex credentials.

### 3. Install Python dependencies and configure the app

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

For ChatGPT subscription access, keep these settings in `.env`:

```dotenv
LLM_PROVIDER=codex
LLM_MODEL=gpt-6-luna
DB_PATH=data/aml_synthetic.db
```

Leave unused API keys empty. If Codex is installed outside PATH, add its actual
native executable path:

```dotenv
CODEX_CLI_PATH=C:/path/to/codex.exe
```

On Windows the adapter requires `codex.exe`, rather than a `.cmd` or `.bat` launcher.
Check `Get-Command codex | Select-Object Source` to see what PowerShell resolves.

Dependency versions in `requirements.txt` are currently unpinned; a fresh install
may resolve newer releases than the environment used during development.

### 4. Initialize the sample database and run tests

For a **fresh sample database**:

```powershell
.\venv\Scripts\python.exe data/scripts/create_schema.py
.\venv\Scripts\python.exe data/scripts/seed_database.py
.\venv\Scripts\python.exe -m pytest tests -q
```

`create_schema.py` drops and recreates the application tables. To retain an existing
database, copy `data/aml_synthetic.db` to the new laptop and **skip both database
initialization commands**, then run the tests. SQLite needs no separate server.

The tests exercise local evidence tools, streaming, and the Codex protocol using
stubs; they do not make subscription-backed model requests.

### 5. Start the web interface

```powershell
.\venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The header should show
`ChatGPT via Codex` and `gpt-6-luna`. Select a sample alert and start an investigation
to verify the signed-in account can use the selected model.

For subsequent launches, run the server command again from the project root.
Restart the server after changing `.env`. For development, append `--reload` to
reload Python source changes automatically.

An investigation can also run from the terminal:

```powershell
.\venv\Scripts\python.exe run_investigation.py tests/sample_alerts/true_positive.json
.\venv\Scripts\python.exe run_investigation.py tests/sample_alerts/false_positive.json
```

## macOS and Linux

Install Python 3.13 and the native Codex CLI for your platform, sign in with
`codex login`, and use these equivalents from the project root:

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
cp .env.example .env

# For a fresh sample database only:
venv/bin/python data/scripts/create_schema.py
venv/bin/python data/scripts/seed_database.py

venv/bin/python -m pytest tests -q
venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

The same `.env` settings and database-preservation instructions apply.

## Configuration

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `codex`, `groq`, `gemini`, `deepseek`, `cerebras`, `mistral`, `nvidia`, or `llamacpp` |
| `LLM_MODEL` | Model override. The example selects `gpt-6-luna`; clear it to use the selected provider's default. |
| `CODEX_CLI_PATH` | Optional native Codex executable path; otherwise resolved from PATH |
| `CODEX_TIMEOUT_SECONDS` | Total timeout for each Codex model turn, including startup; default `300` |
| `DB_PATH` | SQLite database path; default `data/aml_synthetic.db`, relative to the project root |
| `GROQ_API_KEY` / `GROQ_API_KEYS` | Single or comma-separated Groq keys, with rotation on rate limits |
| `GEMINI_API_KEY` | Gemini credential |
| `OPENROUTER_API_KEY` | OpenRouter credential for the `deepseek` provider |
| `CEREBRAS_API_KEY` | Cerebras credential |
| `MISTRAL_API_KEY` | Mistral credential |
| `NVIDIA_API_KEY` | NVIDIA NIM credential |
| `LLAMACPP_HOST` | llama.cpp server URL; default `http://localhost:8080` |

When switching from Codex to another provider, change `LLM_PROVIDER`, update or
clear `LLM_MODEL`, and supply that provider's credential if required.

## How the ChatGPT integration works

1. `agent/llm.py` creates the LangChain-compatible `ChatCodex` adapter.
2. `agent/codex_transport.py` starts `codex app-server` and communicates over local
   stdin/stdout using the [app-server protocol](https://learn.chatgpt.com/docs/app-server).
3. Codex loads the local ChatGPT login and handles authentication/token renewal.
   The app does not read or copy its credential files.
4. Each model turn uses an ephemeral conversation in a temporary directory with a
   read-only sandbox and Codex shell, web, and app tools disabled.
5. The model requests evidence through a structured JSON envelope. LangGraph
   executes the application tools against SQLite and sends the evidence back.
6. Public text deltas flow through LangChain and FastAPI SSE into the dashboard
   and SAR editor. `agent/json_content_stream.py` incrementally decodes the
   envelope's text, including escaped characters, without displaying its wrapper.

Transport deltas may contain one or several tokens. Text appears as it arrives;
tool requests execute only after successful turn completion and validation.
Private Codex reasoning and CLI diagnostics are not forwarded to the interface.
Failed or interrupted turns report an error and never produce a completed verdict.

## Local files and source control

`.gitignore` excludes local environment files, virtual environments, Codex/cloud
credential directories, common credential/key files, databases and their journals,
logs, caches, and generated output directories. `.env.example` is intentionally
tracked and contains empty credential fields.

- Keep real/private input data in `data/private/` or `data/local/`.
- Keep investigation exports and SAR reports in `exports/`, `reports/`, `output/`,
  `outputs/`, or `artifacts/`.
- The synthetic CSVs in `data/csv/` and alert fixtures in `tests/sample_alerts/`
  remain versioned so a fresh checkout can recreate the demo database.
- A Git clone excludes `.env`, `venv/`, and the local database. Recreate those on
  the new laptop, or transfer the database separately when retaining its contents.

Ignore rules do not remove files already tracked by Git and cannot identify every
secret or private document. If a credential was committed, revoke or rotate it
with its provider; removing it from the current files does not remove historical
copies. Git-history cleanup is a separate operation that needs coordination with
other clones. Review staged files before committing:

```powershell
git status --short
git diff --cached --stat
git check-ignore -v .env data/aml_synthetic.db
```

## Troubleshooting

| Symptom | Action |
|---------|--------|
| Codex executable not found, or a `.cmd` wrapper is rejected | Install the native CLI, reopen the terminal after PATH changes, or set `CODEX_CLI_PATH`. |
| ChatGPT login required | Run `codex login` and `codex login status` as the user running the server. |
| Request fails with model/account access or usage limits | Confirm `LLM_MODEL` is available to the signed-in ChatGPT account and check its usage allowance. |
| Model turn times out | Retry or increase `CODEX_TIMEOUT_SECONDS`, then restart the server. |
| Database/table missing | Check `DB_PATH` and run schema/seed setup for a new demo database. |
| Port 8000 is occupied | Stop the existing server before starting another instance. |
| UI is unstyled | Check connectivity to the Tailwind and Google Fonts CDNs. |

## Project structure

```text
agent/              Model adapters, LangGraph agent, prompts, SAR generation
config/             Versioned AML rules, glossary codes, and legal snippets
data/csv/           Synthetic fixtures
data/scripts/       Database schema and seeding
schemas/            Pydantic alert/verdict models
templates/          Dashboard, SAR editor, rules editor, and browser scripts
tests/              Evidence-tool and streaming tests; sample alerts
tools/internal/     Local investigation tools
api.py              FastAPI routes and SSE endpoints
run_investigation.py CLI entry point
```

## Investigation tools

| Tool | Purpose |
|------|---------|
| `get_customer_profile` | KYC profile with PEP, sanctions, and income flags |
| `get_account_summary` | Accounts, statuses, and dormancy detection |
| `get_transaction_history` | Transaction summaries, samples, and AML signal flags |
| `get_prior_alert_history` | Previous alerts and duplicate SAR checks |
| `screen_watchlist` | Watchlist matching and supporting records |

## AML rules covered

- **RULE-01** — Structuring / Smurfing
- **RULE-02** — Rapid Movement of Funds
- **RULE-03** — High-Risk Jurisdiction Transfer
- **RULE-04** — Transaction-Profile Mismatch
- **RULE-05** — Dormant Account Reactivation
- **RULE-06** — Third-Party Funding
- **RULE-07** — PEP / Sanctions Proximity
- **RULE-08** — Round Tripping / Layering
