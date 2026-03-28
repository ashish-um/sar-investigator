"""
ConfigManager — Singleton class for dynamically loading and serving
AML configuration data (glossary codes, rules, legal snippets) from
JSON files on disk.

The formatted output methods convert the raw JSON structures back into
the Markdown strings expected by the LLM prompts.

Usage:
    from agent.config_manager import config
    config.format_matrix_for_prompt()
    config.format_conditional_rules_for_prompt()
"""

import json
import os

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")


class ConfigManager:
    """Singleton manager for all dynamic AML configuration."""

    _instance = None
    glossary_codes: dict
    aml_rules: dict
    legal_snippets: dict

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self.reload()
            self._loaded = True

    # ── I/O ────────────────────────────────────────────────────────

    def reload(self):
        """(Re-)load all configuration JSON files from disk."""
        glossary_path = os.path.join(_CONFIG_DIR, "glossary_codes.json")
        with open(glossary_path, "r", encoding="utf-8") as f:
            self.glossary_codes = json.load(f)

        aml_rules_path = os.path.join(_CONFIG_DIR, "aml_rules.json")
        with open(aml_rules_path, "r", encoding="utf-8") as f:
            self.aml_rules = json.load(f)

        legal_snippets_path = os.path.join(_CONFIG_DIR, "legal_snippets.json")
        with open(legal_snippets_path, "r", encoding="utf-8") as f:
            self.legal_snippets = json.load(f)

    def save_glossary_codes(self, new_data: dict):
        """Persist updated glossary codes to disk and reload into memory."""
        glossary_path = os.path.join(_CONFIG_DIR, "glossary_codes.json")
        with open(glossary_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        self.reload()

    def save_aml_rules(self, new_data: dict):
        """Persist updated AML rules to disk and reload into memory."""
        aml_rules_path = os.path.join(_CONFIG_DIR, "aml_rules.json")
        with open(aml_rules_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        self.reload()

    def save_legal_snippets(self, new_data: dict):
        """Persist updated legal snippets to disk and reload into memory."""
        legal_snippets_path = os.path.join(_CONFIG_DIR, "legal_snippets.json")
        with open(legal_snippets_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        self.reload()

    # ── Prompt Formatters ──────────────────────────────────────────

    def format_matrix_for_prompt(self) -> str:
        """Return the rules-to-codes matrix as a Markdown table string."""
        rows = self.glossary_codes.get("rules_to_codes_matrix", [])
        lines = [
            "| Rule    | Title                        | Primary Codes         | Conditional Codes                              |",
            "|---------|------------------------------|-----------------------|------------------------------------------------|",
        ]
        for r in rows:
            primary = " ".join(r["primary_codes"]) if r["primary_codes"] else "None (narrative only)"
            conditional = " ".join(r["conditional_codes"])
            lines.append(
                f"| {r['rule_id']:<7} | {r['title']:<28} | {primary:<21} | {conditional:<46} |"
            )
        return "\n".join(lines)

    def format_conditional_rules_for_prompt(self) -> str:
        """Return conditional code decision rules as a Markdown bulleted list."""
        rules = self.glossary_codes.get("conditional_code_decision_rules", {})
        lines = []
        for code, description in rules.items():
            lines.append(f"- **{code}** — {description}")
        return "\n".join(lines)


# ── Global singleton instance ──────────────────────────────────────
config = ConfigManager()
