"""Answers through any service that speaks the OpenAI chat format: OpenAI, Gemini, xAI, Groq, Mistral, OpenRouter,
and models running on this Mac through Ollama or LM Studio.

One call per line: the answer itself says SKIP when the line is not a question (no separate check), and the
documents sit at the start of the system message so services with automatic prompt caching reuse them.
Services differ in which optional request fields they accept: a field a service refuses is dropped after the
first refusal and the call is repeated without it.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

from .answer import Answer, Style, Usage, instructions
from .claude_code import GATE
from .providers import Provider


def _reasoning(provider_id: str, model: str) -> dict:
    """Ask for as little thinking as the model allows: a live answer cannot wait."""
    name = model.split("/")[-1]
    if provider_id in ("openai", "openrouter"):
        found = re.match(r"gpt-(\d+)(?:\.(\d+))?", name)
        if found and int(found.group(1)) >= 5:
            return {"reasoning_effort": "none" if found.group(2) else "minimal"}  # 5.1 and later accept "none"
    if provider_id == "groq" and name.startswith("gpt-oss"):
        return {"reasoning_effort": "low"}
    if provider_id == "gemini" and re.match(r"gemini-(2\.5|[3-9])", name):
        return {"reasoning_effort": "none" if "flash" in name else "low"}
    return {}


class OpenAICopilot:
    gatekeeps = True
    HISTORY_TURNS = 3

    def __init__(self, material: str, situation: str, provider: Provider, key: str, model: str,
                 style: Style | None = None):
        from openai import OpenAI
        self.provider = provider
        self.client = OpenAI(api_key=key, base_url=provider.base_url, timeout=60)
        self.style = style or Style()
        self.model = model
        self.system = instructions(situation, self.style) + "\n" + GATE + "\n\n" + material
        self.history: list[tuple[str, str]] = []
        # optional fields, dropped one by one if the service refuses them
        self.optional = {"stream_options": {"include_usage": True}, **provider.options,
                         **_reasoning(provider.id, model)}
        self.limit_field = "max_completion_tokens" if provider.id == "openai" else "max_tokens"

    def _call(self, content: str, limit: int):
        import openai
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": content}]
        while True:
            try:
                return self.client.chat.completions.create(
                    model=self.model, stream=True, messages=messages, **{self.limit_field: limit}, **self.optional)
            except openai.BadRequestError as error:
                refused = [name for name in self.optional if name in str(error)]
                if not refused and self.optional:
                    refused = list(self.optional)  # the service did not say which: drop them all
                if not refused:
                    raise
                for name in refused:
                    self.optional.pop(name)

    @staticmethod
    def _usage(raw) -> Usage:
        details = getattr(raw, "prompt_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        return Usage((raw.prompt_tokens or 0) - cached, 0, cached, raw.completion_tokens or 0)

    def warm(self) -> Usage:
        """A first short call proves the key and model work and, where the service caches, stores the documents."""
        usage = Usage()
        for chunk in self._call("Last line heard: Thanks for joining.", 16):
            if getattr(chunk, "usage", None):
                usage = self._usage(chunk.usage)
        return usage

    def answer(self, question: str, before: str = "") -> Iterator[str | Answer]:
        started, first, parts, usage = time.perf_counter(), None, [], Usage()
        earlier = "\n\n".join(f"Q: {q}\nA: {a}" for q, a in self.history[-self.HISTORY_TURNS:])
        content = (f"Earlier in this call:\n{earlier}\n\n" if earlier else "") + \
                  (f"Line before: {before}\n" if before else "") + f"Last line heard: {question}"
        stream = self._call(content, 300 + 60 * self.style.lines)
        try:
            for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = self._usage(chunk.usage)
                if chunk.choices and chunk.choices[0].delta.content:
                    if first is None:
                        first = time.perf_counter() - started
                    parts.append(chunk.choices[0].delta.content)
                    yield chunk.choices[0].delta.content
        finally:
            stream.close()  # also when the caller stops reading: the line was not a question
        result = Answer(question, "".join(parts), first or 0.0, time.perf_counter() - started)
        result.usage = usage
        yield result

    def remember(self, question: str, answer: str) -> None:
        self.history = (self.history + [(question, answer)])[-self.HISTORY_TURNS:]
