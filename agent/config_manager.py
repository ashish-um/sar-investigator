"""Load AML rule definitions used by the investigation prompts."""

import json
import os

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")


class ConfigManager:
    """Load the investigator's AML rules from disk."""

    def __init__(self):
        self.reload()

    def reload(self):
        """Reload AML rule definitions and evidence guidelines."""
        aml_rules_path = os.path.join(_CONFIG_DIR, "aml_rules.json")
        with open(aml_rules_path, "r", encoding="utf-8") as f:
            self.aml_rules = json.load(f)


config = ConfigManager()
