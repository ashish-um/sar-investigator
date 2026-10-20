"""Test real pipe I/O, deadlines, and process cleanup with a local Python stub."""

import os
import sys

import pytest

from agent.codex_transport import CodexAppServer


def test_rpc_reads_one_line_without_waiting_for_process_exit(tmp_path):
    script = """import json, sys
for line in sys.stdin:
    request = json.loads(line)
    print(json.dumps({'id': request['id'], 'result': {'ok': True}}), flush=True)
"""
    with CodexAppServer([sys.executable, "-u", "-c", script], cwd=str(tmp_path), env=os.environ.copy(), timeout=5) as server:
        assert server.request("initialize", {}) == {"ok": True}
        assert server.process.poll() is None
    assert server.process.poll() is not None


def test_timeout_terminates_stalled_process(tmp_path):
    with pytest.raises(RuntimeError, match="did not finish"):
        with CodexAppServer([sys.executable, "-c", "import time; time.sleep(30)"], cwd=str(tmp_path), env=os.environ.copy(), timeout=0.1) as server:
            server.receive()
    assert server.process.poll() is not None


def test_unexpected_eof_and_malformed_stream_fail(tmp_path):
    for script, message in [("pass", "disconnected"), ("print('not JSON')", "invalid stream")]:
        with pytest.raises(RuntimeError, match=message):
            with CodexAppServer([sys.executable, "-c", script], cwd=str(tmp_path), env=os.environ.copy(), timeout=5) as server:
                server.receive()
        assert server.process.poll() is not None
