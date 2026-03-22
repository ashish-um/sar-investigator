# AML SAR Investigator Agent – Implementation Details

Welcome to the AML (Anti-Money Laundering) SAR (Suspicious Activity Report) Investigator Agent project! This document explains how the system is architected, how the code works under the hood, and the precise reasoning behind the technical and design decisions we made while building it.

Whether you're a developer joining the team or a stakeholder wanting to understand how the agent reasons, this guide will walk you through it.

---

## 1. What does this project do?

Banks generate thousands of automated alerts every day flagging potentially suspicious customer transactions. Most of these are "false positives" (legitimate activity like receiving an inheritance or moving house). However, some are "true positives" (genuine money laundering, structuring, or illicit funding). 

This project uses an AI Agent powered by **LangChain** and **LangGraph** (with Groq's `llama-3.3-70b-versatile` LLM) to act as a Level 1 AML Investigator. When given an alert, the agent:
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

### The Runner (`agent/runner.py` & `run_investigation.py`)
This is the entry point. It takes a JSON alert file (like `tests/sample_alerts/true_positive.json`), strips it down to an `AlertPayload`, and injects it into the initial `AgentState`. 

Once the graph finishes running, the runner extracts the final JSON verdict from the LLM's last message using a robust Regular Expression (`re.search(r'\{.*\}', ...)`).

**Decision Reason:** We use a regex fallback here because LLMs occasionally output their reasoning text (like `1. ANALYSIS: ...`) in the exact same message as the JSON block, even when told not to. Trying to parse the whole string as JSON would crash the script. The regex ensures we always isolate just the JSON payload.

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

---

## Conclusion

The AML SAR Investigator Agent is not just a chatbot bolted to a database. It is a highly constrained, stateful pipeline where:
1. Python handles the heavy math and data aggregation.
2. The LangGraph state manages the execution loop perfectly.
3. The Prompt enforces a strict, legally defensible standard of reasoning and evidence citation.
4. The Runner safely extracts the final payload regardless of LLM markdown inconsistencies.

By forcing the LLM to adhere to the `ANALYSIS` -> `UPDATED HYPOTHESIS` -> `NEXT STEP` paradigm, the system generates high-quality, auditable AML investigations that parallel the rigor of a human analyst.
