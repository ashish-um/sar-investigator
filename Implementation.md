# AML SAR Investigator Agent – Implementation Details

Welcome to the AML (Anti-Money Laundering) SAR (Suspicious Activity Report) Investigator Agent project! This document explains how the system is architected, how the code works under the hood, and the precise reasoning behind the technical and design decisions we made while building it.

Whether you're a developer joining the team or a stakeholder wanting to understand how the agent reasons, this guide will walk you through it.

---

## 1. What does this project do?

Banks generate thousands of automated alerts every day flagging potentially suspicious customer transactions. Most of these are "false positives" (legitimate activity like receiving an inheritance or moving house). However, some are "true positives" (genuine money laundering, structuring, or illicit funding). 

This project uses an AI Agent powered by **LangChain** and **LangGraph** to act as a Level 1 AML Investigator. The LLM provider is configurable at runtime — currently supporting **Groq** (`llama-3.3-70b-versatile`) and **Google Gemini** (`gemini-2.5-flash`) — with no code changes required to switch between them. When given an alert, the agent:
1. Forms a hypothesis about what the customer is doing.
2. Uses a suite of internal database tools to gather financial evidence.
3. Analyzes the tool results to confirm or refute its hypothesis.
4. Concludes whether the alert is a `TRUE_POSITIVE` or `FALSE_POSITIVE` and generates a detailed JSON report (the SAR recommendation).

---

## 2. Core Architecture

The project is structured around a **StateGraph**—a cyclical loop where the LLM (the brain) and the Tools (the hands) pass data back and forth until the investigation is complete.

### The State (`agent/state.py`)
At the center of the graph is the `AgentState`. It holds the ongoing conversation `messages` (interactions between the user, the AI, and the tools), the original `alert` payload, and the `customer_id`. As the investigation progresses, new messages are appended to this state.

### The Graph (`agent/graph.py`)
The graph has two main nodes:
1. **Agent Node**: Calls the LLM, providing it with the `AgentState` history and the system prompt. The LLM decides what to say and whether to invoke a tool.
2. **Tools Node**: If the LLM requests a tool call, the graph routes the state here. The node executes the requested Python function and returns the result (usually JSON data from the database) as a `ToolMessage`.

The system loops between these two nodes until the Agent Node decides it has enough evidence and outputs the final JSON verdict instead of requesting another tool.

### The LLM Factory (`agent/llm.py`)
The agent is **provider-agnostic**. Instead of hardcoding a specific LLM, `agent/graph.py` calls `get_llm()` from `agent/llm.py`, which reads environment variables to determine the provider, model, and API key:

| Variable | Purpose | Example |
|---|---|---|
| `LLM_PROVIDER` | Which provider to use | `groq`, `gemini`, or `deepseek` |
| `LLM_MODEL` | Optional model override | `gemini-2.5-flash` (blank = provider default) |
| `GROQ_API_KEY` | Groq key(s) — comma-separated for key hopping | `gsk_key1,gsk_key2` |
| `GEMINI_API_KEY` | Google Gemini API key | — |
| `OPENROUTER_API_KEY` | OpenRouter key (for DeepSeek via OpenRouter) | — |

`get_llm()` validates the API key is present, imports the correct LangChain chat model, and returns it. All three providers share the `BaseChatModel` interface, so nothing downstream needs to know which provider is active.

The **DeepSeek** provider uses `ChatOpenAI` from `langchain-openai` with `base_url` pointed at `https://openrouter.ai/api/v1`. OpenRouter exposes an OpenAI-compatible API, so no DeepSeek-specific package is needed.

**Decision Reason:** We use lazy imports (importing inside the function) so that `langchain-groq` is not required when using Gemini and vice versa. This keeps the dependency footprint minimal and allows switching providers at runtime by editing `.env` alone.

#### Groq Key Hopping
Groq's free tier has aggressive rate limits (429 errors). To handle this transparently, `get_llm()` returns a `_KeyHoppingGroq` wrapper when the provider is Groq. This wrapper:

1. Reads all API keys from `GROQ_API_KEY` or `GROQ_API_KEYS` (both accept comma-separated values).
2. Stores them in a `_GroqKeyPool` (round-robin index).
3. Overrides `_generate()` and `_stream()` to catch `groq.RateLimitError`.
4. On a 429, it rotates to the next key, rebuilds the internal HTTP client, and retries.
5. Each key is tried once. If all keys are exhausted, the error is raised.

**Decision Reason:** The retry is implemented as a `ChatGroq` subclass rather than external retry middleware so that key rotation happens *inside* the model — the graph, runner, and tools are completely unaware of it. This also means the retry catches errors mid-stream (during `_stream()`), not just on the initial request.

### The Interfaces (`agent/runner.py`, `run_investigation.py`, and `api.py`)
The system has two entry points that both orchestrate the same underlying graph:

1. **CLI (`run_investigation.py`)**: Takes a JSON alert file, strips it down to an `AlertPayload`, and injects it into the initial `AgentState`. 
2. **API (`api.py`)**: A FastAPI application providing a `POST /investigate` endpoint. It accepts the `AlertPayload` as a JSON body.

Both interfaces use `graph.stream(..., stream_mode="messages")`. This streams the LLM's "Chain of Thought" back to the user token-by-token in real-time. 

In the API, this streaming is exposed as **Server-Sent Events (SSE)**. The endpoint yields events for `thinking` (raw tokens), `tool_call` (tool name and parsed args), `tool_result` (JSON data from the database), and the final `verdict`. The CLI instead prints these to `stdout`.

Instead of waiting 15-20 seconds for the entire graph to execute and print the results in one large batch, the runner uses `graph.stream(..., stream_mode="messages")`. This streams the LLM's "Chain of Thought" back to the user token-by-token in real-time. It also uses a robust chunk accumulator to construct and display tool calls the moment the LLM decides to use them.

Once the investigation finishes, the runner extracts the final JSON verdict from the accumulated reasoning text using a robust Regular Expression (`re.search(r'\{.*\}', ...)`).

**Decision Reason:** We use a regex fallback here because LLMs occasionally output their reasoning text (like `1. ANALYSIS: ...`) in the exact same message as the JSON block, even when told not to. Trying to parse the whole string as JSON would crash the script. The regex ensures we always isolate just the JSON payload.

**Key Design Decision: Cross-Provider Content Compatibility**
Different LLM providers return streaming content in different formats — Groq returns `chunk.content` as a plain string, while Gemini returns it as a list of dictionaries (multimodal format). The runner uses a `_extract_text()` helper function that normalises both formats into plain text, ensuring the streaming output and verdict extraction work identically regardless of which provider is active.

---

## 3. The Investigation Tools

The LLM cannot query the database directly. Instead, we provide it with four specific, highly constrained Python tools (found in `tools/internal/`). 

### Tool 1: `get_customer_profile`
- **What it does:** Retrieves KYC (Know Your Customer) data, declared income, occupation, and computes risk flags like PEP (Politically Exposed Person) status and document expiry.
- **Why we built it:** You cannot investigate a transaction without knowing who the customer is. A £50,000 transfer is normal for a corporate CEO but highly suspicious for a minimum-wage retail worker. 

### Tool 2: `get_account_summary`
- **What it does:** Retrieves all accounts held by the customer, their balances, and computes dormancy flags.
- **Why we built it:** It provides the `account_id` needed to look up transactions. We also compute `days_since_last_activity` against the `observation_window_end` of the alert—not today's date—to determine if the account was dormant when the suspicious activity happened. 

### Tool 3: `get_transaction_history`
- **What it does:** Fetches transactions for a specific account over the alert window and computes behavioral signals like `structuring_presignal` (deposits clustered just below the £10,000 reporting threshold) or `rapid_outflow_detected`.
- **Why we built it:** LLMs are terrible at math and scrolling through hundreds of raw database rows. If we gave the LLM raw data, it would hallucinate totals. Instead, our Python code does the heavy lifting (summing totals, calculating retention ratios, finding high-risk transfers) and returns these *pre-computed signals* to the LLM.

### Tool 4: `get_prior_alert_history`
- **What it does:** Retrieves previous alerts and their dispositions (e.g., whether a human analyst previously marked similar activity as a false positive because the money was just an inheritance).
- **Why we built it:** Context is paramount. If a human already cleared this exact activity for this customer three months ago, an automated agent shouldn't flag it again. It also prevents the agent from filing duplicate SARs for the same activity window, which is legally prohibited by the NCA.

**Key Design Decision: Parameter Hallucination Prevention**
Every tool's docstring explicitly states: `"Only the parameters listed below are accepted. Do not pass any additional parameters."` We added this because LLMs have a habit of "hallucinating" parameters that don't exist in the function signature if they think it will help (like trying to pass a date filter to the customer profile tool). This strict instruction prevents runtime crashes.

**Key Design Decision: Token Efficiency & Context Management**
To prevent the LLM's context window from filling up with raw database dumps (which wastes thousands of tokens and degrades reasoning), tools return **summaries and computed flags** in full, but aggressively truncate raw data arrays. For example, `get_transaction_history` returns a full statistical summary (total transactions, net change, retention ratio, etc.) and computed flags, but truncates the raw transactions array to only the Top 5 largest events. Similarly, `get_prior_alert_history` only returns the Top 3 most recent alerts alongside the full risk context.

Furthermore, tool outputs are intentionally restructured to push "signal" to the top. The keys `SUMMARY` and `COMPUTED_FLAGS` are capitalized and placed at the very beginning of the JSON response. Because LLMs read down a document linearly, this serves as a visual anchor, ensuring the model pays the most attention to the most mathematically critical evidence rather than getting lost in the noise of raw arrays.

**Key Design Decision: Smart Transaction Sampling**
The sample selection in `get_transaction_history` is not a naive "top 5 by amount." It uses context-aware logic:
- **High-risk jurisdiction transactions are always included** in the sample, appended *on top of* the regular top 5 — never replacing one of them. This guarantees the SWIFT transfer to a sanctioned country always appears alongside all structured cash deposits.
- **When `structuring_presignal` is true**, the 5 regular slots prioritize sub-threshold credit transactions (£8,000–£9,999) instead of largest-by-amount. This ensures all structured deposits and their unique transaction IDs are visible to the LLM.
- This design prevents a critical data accuracy bug: if high-risk transactions *replaced* a regular slot, the LLM would lack enough transaction IDs to correctly populate evidence entries across multiple rules.

---

## 4. The Agent Brain: Prompts & Reasoning Discipline

The core intelligence of the agent lives in `agent/prompts.py`. This is easily the most critical file in the project. 

If you just tell an LLM "investigate this," it will randomly guess an answer without writing down its thoughts. To fix this, we engineered a strict **Reasoning Discipline** that forces the LLM to "think out loud."

The prompt forces the LLM to output exactly one of two formats for every response:

**FORMAT A: Before calling the first tool**
1. **INITIAL HYPOTHESIS**: What it thinks is happening based on the alert alone.
2. **NEXT STEP**: What tool it wants to call and why.

**FORMAT B: After receiving any tool result**
1. **ANALYSIS**: What the database just returned. It MUST cite specific numbers.
2. **UPDATED HYPOTHESIS**: How this data proved or disproved the previous hypothesis.
3. **NEXT STEP**: What tool to call next, or "INVESTIGATION COMPLETE".

**Decision Reason:** Why force this structure? Because it prevents the LLM from taking shortcuts. If it receives an account summary, it *must* write down its analysis of the balance before it is allowed to ask for transaction history. This makes the agent's logic auditable for a human reviewer.

### The "Critical Evidence Rule"

A SAR (Suspicious Activity Report) is a legal document. Saying "the customer made multiple large transfers" is not good enough for law enforcement. You must be specific.

We added an aggressive rule to the prompt that rejects generic phrasing:
> **BAD**: "Multiple cash deposits below threshold"
> **GOOD**: "5 cash deposits between £9,500 and £9,900"

**Decision Reason:** We force the LLM to extract the exact monetary values, transaction counts, and ratios returned by the Python tools and place them into the final JSON output. This guarantees that human analysts reading the AI's recommendation are given actionable, mathematically accurate evidence. Furthermore, this rule applies to *exculpatory* (innocent) evidence as well. If the verdict is `FALSE_POSITIVE`, the agent must cite exactly *why* the activity is innocent, pulling directly from prior analyst notes or verifiable data constraints.

### Enhanced SAR Evidence Schema

The `key_evidence` entries in the final verdict are not simple one-liners. Each entry is a self-contained evidence record with six fields:

| Field | Purpose |
|---|---|
| `rule_mapped` | Which AML rule this evidence supports (e.g., `RULE-01`) |
| `finding` | One sentence with specific amounts, counts, dates, and counterparty names |
| `supporting_data` | Structured object with `amounts`, `dates`, `counterparties`, `accounts_involved`, and `transaction_ids` — always as arrays |
| `regulatory_significance` | Why this pattern is suspicious under the cited regulation |
| `source_table` | Which database table this evidence was drawn from |
| `statistical_context` | A mandatory calculated metric comparing the finding to the customer's baseline profile |

**Decision Reason:** A SAR analyst reading only one `key_evidence` entry — with no other context — must be able to understand exactly what happened, who was involved, why it is suspicious, and how it compares to the customer's declared profile. The old schema (`data_point` + `significance`) produced headlines, not evidence.

### Evidence Construction Rules

The prompt includes strict guardrails for evidence quality:

1. **Rule-Evidence Completeness**: Every rule in `rules_triggered` must have a corresponding `key_evidence` entry. Three rules = three entries.
2. **Unique Transaction IDs**: Transaction IDs must never be reused across evidence entries. Each ID belongs to exactly one transaction.
3. **Array-Only Fields**: `supporting_data` fields must always be arrays, even for single values. No singular field names like `amount` or `date`.
4. **Source Segregation**: RULE-07 (PEP) evidence must only contain customer profile fields (`pep_flag`, `risk_rating`, `kyc_status`), not transaction data. Transaction evidence belongs in RULE-01 or RULE-03 entries.
5. **Mandatory Statistical Context**: Each rule type requires specific calculated figures:
   - **RULE-01**: Total structured amount as a percentage of declared annual income
   - **RULE-02**: Retention ratio and credit-to-debit time gap
   - **RULE-03**: Outflow as a percentage of total credits, plus retention ratio
   - **RULE-04/07**: Income multiple of flagged amount vs. declared income

### FORMAT B Enforcement

The prompt now includes explicit "critical violation" language ensuring the LLM writes all three FORMAT B steps (`ANALYSIS → UPDATED HYPOTHESIS → NEXT STEP`) after *every* tool result — including results that show no suspicious flags. Skipping FORMAT B and proceeding directly to a tool call is flagged as a critical violation. This prevents the agent from silently consuming benign results without documenting its reasoning.

---

## Conclusion

The AML SAR Investigator Agent is not just a chatbot bolted to a database. It is a highly constrained, stateful pipeline where:
1. Python handles the heavy math and data aggregation.
2. The LangGraph state manages the execution loop perfectly.
3. The Prompt enforces a strict, legally defensible standard of reasoning and evidence citation.
4. The Runner safely extracts the final payload regardless of LLM markdown inconsistencies.

By forcing the LLM to adhere to the `ANALYSIS` -> `UPDATED HYPOTHESIS` -> `NEXT STEP` paradigm, the system generates high-quality, auditable AML investigations that parallel the rigor of a human analyst.
