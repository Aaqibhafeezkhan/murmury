"""Answers through the user's own Claude Code login instead of an API key.

Each line goes to a `claude` process started in advance, so its start-up time is already paid when the
line arrives (measured: first text 0.9 s, the same as the API). One process per line: when the line was
not a question the process is closed, and nothing it wrote stays in a session. There is no separate
question check, because a Claude Code call is too slow for it (3 to 8 s measured with Haiku): the answer
model itself replies SKIP to a line that is not a question.

The documents go to the process as a system-prompt file in a private temporary folder, removed on exit.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from .answer import Answer, Style, Usage, instructions

SKIP = "SKIP"
GATE = f"""
The message gives the last line heard on the call, after the earlier questions and answers. If that line \
is not a question or a request for information addressed to the user (thanks, greetings, small talk, \
agreement, a comment, the speaker talking about themselves), reply exactly {SKIP} and nothing else. A short \
follow-up that only names a topic or a figure ("and the margin in year three?") is a question."""


def claude_path() -> str | None:
    """The `claude` command: on PATH, or where its installer puts it (an app started from Finder has a short PATH)."""
    found = shutil.which("claude")
    if found:
        return found
    for candidate in (Path.home() / ".local/bin/claude", Path("/opt/homebrew/bin/claude"), Path("/usr/local/bin/claude")):
        if candidate.exists():
            return str(candidate)
    return None


INSTALL_URL = "https://docs.anthropic.com/en/docs/claude-code/setup"


def status() -> dict:
    """Whether Claude Code is installed and signed in: {"installed", "signed_in", "plan", "method"}."""
    command = claude_path()
    if not command:
        return {"installed": False, "signed_in": False}
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        out = subprocess.run([command, "auth", "status", "--json"], capture_output=True, text=True, timeout=15, env=env)
        info = json.loads(out.stdout)
    except Exception:
        return {"installed": True, "signed_in": False}
    return {"installed": True, "signed_in": bool(info.get("loggedIn")), "plan": info.get("subscriptionType") or "",
            "method": info.get("authMethod") or ""}


def open_sign_in() -> None:
    """Sign-in needs a browser and a terminal: open Terminal with the login command."""
    command = claude_path() or "claude"
    subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{command} auth login"',
                      "-e", 'tell application "Terminal" to activate'])


class ClaudeCodeCopilot:
    gatekeeps = True  # the answer itself says SKIP for a line that is not a question
    HISTORY_TURNS = 3
    SPARE = 2          # processes kept started: one takes 2-3 s to start, and lines can come close together
    FIRST_TEXT_LIMIT = 6.0  # seconds without any text before the process is replaced (one reply took 37 s)

    def __init__(self, material: str, situation: str, model: str, style: Style | None = None):
        self.command = claude_path()
        if not self.command:
            raise RuntimeError("Claude Code is not installed: install it, or choose 'API key' on the setup screen")
        self.model = model
        self.style = style or Style()
        self.folder = Path(tempfile.mkdtemp(prefix="murmury-"))  # private to the user (mode 700)
        atexit.register(shutil.rmtree, self.folder, True)
        self.prompt = self.folder / "system.txt"
        self.prompt.write_text(instructions(situation, self.style) + "\n" + GATE + "\n\n" + material, encoding="utf-8")
        # an API key in the environment would make `claude` bill it instead of using the user's login
        self.env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        self.history: list[tuple[str, str]] = []
        self.lock = threading.Lock()
        self.ready: list[subprocess.Popen] = []

    def _spawn(self) -> subprocess.Popen:
        return subprocess.Popen(
            [self.command, "-p", "--model", self.model, "--system-prompt-file", str(self.prompt), "--tools", "",
             "--effort", "low", "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
             "--input-format", "stream-json", "--output-format", "stream-json", "--include-partial-messages",
             "--verbose"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            cwd=self.folder, bufsize=1, env=self.env)

    def _take(self) -> subprocess.Popen:
        """The oldest process started in advance (the readiest), and start a replacement."""
        with self.lock:
            self.ready = [p for p in self.ready if p.poll() is None]
            process = self.ready.pop(0) if self.ready else None
        threading.Thread(target=self._fill, daemon=True).start()
        return process or self._spawn()

    def _fill(self) -> None:
        with self.lock:
            while len(self.ready) < self.SPARE:
                self.ready.append(self._spawn())

    def close(self) -> None:
        with self.lock:
            for p in self.ready:
                p.kill()
            self.ready = []

    def _stream(self, process: subprocess.Popen, content: str) -> Iterator[tuple[str, object]]:
        process.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
        process.stdin.flush()
        for line in process.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "stream_event":
                delta = event["event"].get("delta", {})
                if event["event"].get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                    yield "text", delta["text"]
            elif event.get("type") == "result":
                if event.get("is_error"):
                    raise RuntimeError(f"Claude Code: {event.get('result') or event.get('subtype')}")
                yield "usage", event.get("usage", {})
                return

    @staticmethod
    def _usage(raw: dict) -> Usage:
        return Usage(raw.get("input_tokens", 0), raw.get("cache_creation_input_tokens", 0),
                     raw.get("cache_read_input_tokens", 0), raw.get("output_tokens", 0))

    def warm(self) -> Usage:
        """Put the documents in the cache before the call, and have the first process waiting."""
        process, usage = self._take(), Usage()
        try:
            for kind, value in self._stream(process, f"Last line heard: Thanks for joining.\n(Reply {SKIP}.)"):
                if kind == "usage":
                    usage = self._usage(value)
        finally:
            process.kill()
        return usage

    def answer(self, question: str, before: str = "") -> Iterator[str | Answer]:
        started, first, parts = time.perf_counter(), None, []
        earlier = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in self.history[-self.HISTORY_TURNS:])
        content = (f"Earlier in this call:\n{earlier}\n\n" if earlier else "") + \
                  (f"Line before: {before}\n" if before else "") + f"Last line heard: {question}"
        usage = Usage()
        for attempt in range(2):  # a process silent for FIRST_TEXT_LIMIT seconds is replaced once
            process = self._take()
            watchdog = threading.Timer(self.FIRST_TEXT_LIMIT, lambda p=process: first is None and p.kill())
            watchdog.start()
            try:
                for kind, value in self._stream(process, content):
                    if kind == "text":
                        if first is None:
                            first = time.perf_counter() - started
                            watchdog.cancel()
                        parts.append(value)
                        yield value
                    else:
                        usage = self._usage(value)
            finally:
                watchdog.cancel()
                process.kill()  # also when the caller stops reading: the line was not a question
            if first is not None:
                break
        result = Answer(question, "".join(parts), first or 0.0, time.perf_counter() - started)
        result.usage = usage
        yield result

    def remember(self, question: str, answer: str) -> None:
        self.history = (self.history + [(question, answer)])[-self.HISTORY_TURNS:]
