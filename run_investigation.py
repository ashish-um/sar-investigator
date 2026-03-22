# Entry point to run a single investigation from a sample alert file
# Usage: python run_investigation.py tests/sample_alerts/true_positive.json

import json
import sys
from schemas.alert import AlertPayload
from agent.runner import run_investigation

if __name__ == "__main__":
    alert_file = sys.argv[1] if len(sys.argv) > 1 else "tests/sample_alerts/true_positive.json"
    with open(alert_file) as f:
        alert_data = json.load(f)
    alert = AlertPayload(**alert_data)
    run_investigation(alert)
