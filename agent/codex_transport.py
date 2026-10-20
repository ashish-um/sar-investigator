"""Small, cancellable stdio client for Codex app-server JSON-RPC."""

import json
import os
from queue import Empty, Queue
import subprocess
from threading import Thread
from time import monotonic


class CodexAppServer:
    def __init__(self, command, *, cwd, env, timeout):
        self.command = command
        self.cwd = cwd
        self.env = env
        self.timeout = timeout
        self.process = None
        self.reader = None
        self.inbox = Queue()
        self.next_id = 0

    def __enter__(self):
        self.deadline = monotonic() + self.timeout
        self.process = subprocess.Popen(
            self.command, cwd=self.cwd, env=self.env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="strict", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.reader = Thread(target=self._read_stdout, daemon=True)
        self.reader.start()
        return self

    def _read_stdout(self):
        try:
            for line in self.process.stdout:
                if line.strip():
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError("Invalid JSON-RPC message")
                    self.inbox.put(message)
        except (ValueError, OSError) as exc:
            self.inbox.put(exc)
        finally:
            self.inbox.put(None)

    def send(self, method, params=None, *, request=False):
        message = {"method": method, "params": params or {}}
        if request:
            self.next_id += 1
            message["id"] = self.next_id
        try:
            self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError("Codex app-server disconnected before the request completed.") from exc
        return message.get("id")

    def receive(self):
        try:
            message = self.inbox.get(timeout=max(0, self.deadline - monotonic()))
        except Empty as exc:
            raise RuntimeError(
                f"Codex did not finish within {self.timeout:g} seconds. "
                "Retry or increase CODEX_TIMEOUT_SECONDS in .env."
            ) from exc
        if isinstance(message, Exception):
            raise RuntimeError("Codex app-server returned an invalid stream.") from message
        if message is None:
            raise RuntimeError("Codex disconnected before completing the response.")
        if "method" in message and "id" in message:
            # This backend doesn't grant tool approvals or execute server requests.
            self.process.stdin.write(json.dumps({
                "id": message["id"],
                "error": {"code": -32601, "message": "Client-side tools are disabled."},
            }) + "\n")
            self.process.stdin.flush()
            raise RuntimeError("Codex requested an unsupported client-side action.")
        if "error" in message:
            raise RuntimeError(
                "Codex rejected the app-server request. Check your CLI version, "
                "ChatGPT login, and model access."
            )
        return message

    def request(self, method, params=None):
        request_id = self.send(method, params, request=True)
        while True:
            message = self.receive()
            if message.get("id") == request_id:
                return message.get("result", {})

    def __exit__(self, *exc):
        # Also runs on cancellation/GeneratorExit and on a failed partial turn.
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.stdin.close()
        self.reader.join(timeout=1)
        self.process.stdout.close()
