"""From a finished line to what the window shows, with the question check and the live answer in parallel.

The live answer starts at once, while a fast model decides whether the line is a question and whether a
prepared answer covers it. Not a question: the live answer is dropped. Prepared: it is shown at once,
and the live answer replaces it when complete. New question: the live answer streams as it arrives.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass

from .answer import Answer, Prepared, PreparedCopilot


@dataclass(frozen=True)
class Show:
    kind: str  # "prepared", "live-chunk", "live-done", "dropped"
    text: str
    at: float  # time.perf_counter()


def respond(copilot: PreparedCopilot, line: str, before: str = "") -> Iterator[Show]:
    if getattr(copilot, "gatekeeps", False):
        yield from respond_gated(copilot, line, before)
        return
    events: queue.Queue = queue.Queue()
    stop = threading.Event()

    def check() -> None:
        events.put(("verdict", copilot.classify(line, before)))

    def write() -> None:
        for part in copilot.answer(line):
            if stop.is_set():
                return  # leaving the stream closes the request: no more tokens billed
            events.put(("done", part) if isinstance(part, Answer) else ("chunk", part))

    threading.Thread(target=check, daemon=True).start()
    threading.Thread(target=write, daemon=True).start()

    verdict, decided, held = None, False, []
    while True:
        kind, value = events.get()
        if kind == "verdict":
            verdict, decided = value, True
            if verdict is None:
                stop.set()
                yield Show("dropped", "", time.perf_counter())
                return
            if isinstance(verdict, Prepared):
                yield Show("prepared", verdict.answer, time.perf_counter())
            elif held:
                yield Show("live-chunk", "".join(held), time.perf_counter())
                held = []
        elif kind == "chunk":
            if not decided:
                held.append(value)
            elif verdict == "NEW":
                yield Show("live-chunk", value, time.perf_counter())
        elif kind == "done":
            if not decided:  # the answer finished before the check: wait for the verdict
                while (item := events.get())[0] != "verdict":
                    pass
                verdict, decided = item[1], True
                if verdict is None:
                    yield Show("dropped", "", time.perf_counter())
                    return
            yield Show("live-done", value.text, time.perf_counter())
            return


def respond_gated(copilot, line: str, before: str = "") -> Iterator[Show]:
    """For a copilot whose answer itself says SKIP when the line is not a question (Claude Code)."""
    from .claude_code import SKIP

    stream = copilot.answer(line, before)
    held = ""
    for part in stream:
        if isinstance(part, Answer):
            if part.text.strip().upper().startswith(SKIP):
                yield Show("dropped", "", time.perf_counter())
            else:
                if held:
                    yield Show("live-chunk", held, time.perf_counter())
                yield Show("live-done", part.text, time.perf_counter())
            return
        if held is not None and len(held) < len(SKIP):
            held += part
            if len(held.strip()) < len(SKIP):
                continue
            if held.strip().upper().startswith(SKIP):
                stream.close()  # closes the process: no more tokens
                yield Show("dropped", "", time.perf_counter())
                return
            yield Show("live-chunk", held, time.perf_counter())
            held = None
        else:
            yield Show("live-chunk", part, time.perf_counter())
