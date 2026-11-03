"""Question detection and answers, with Claude, from the chosen material only.

Both steps use the fastest model; the material sits in the prompt cache for the whole call, so each
question pays only a fraction of the material's tokens.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
import re
from dataclasses import dataclass, field

import anthropic

DETECT_MODEL = "claude-haiku-4-5"
ANSWER_MODEL = "claude-haiku-4-5"

@dataclass
class Style:
    """How answers look, chosen on the setup screen. The defaults are the tuned ones (evals/run.py)."""
    say_words: int = 12   # the SAY line, at most
    lines: int = 3        # fact lines under it, at most (the window shows no more)
    line_words: int = 14  # words per line, at most: a short spoken sentence
    numbers: int = 1      # numbers per fact line, at most
    sources: bool = True
    tone: str = "confident"   # confident, neutral, cautious
    language: str = ""        # empty: the language of the question
    extra: str = ""           # the user's own instructions
    format: str = "talking"   # talking (spoken sentences), facts (label: data), script (read as is)


PRESETS = {
    "Short": Style(say_words=10, lines=2, line_words=10),
    "Standard": Style(),
    "Detailed": Style(say_words=16, lines=5, line_words=18, numbers=2),
}

TONES = {
    "confident": """- Speak for the user, as they would defend their own plan. Do not volunteer weaknesses unless the \
question asks about risks; then answer plainly with the plan's response. Never open the SAY line with a \
negation ("No", "Not", "Non"): say what is true instead.""",
    "neutral": """- State the facts plainly and evenly, without selling. Mention a limit only when the material gives \
one and it bears on the question.""",
    "cautious": """- Be careful and precise: say whether each figure is measured, estimated or forecast, and give the \
main limit the material states when it bears on the question.""",
}

ANSWER_INSTRUCTIONS = """You help the user during a live call: {situation}. Someone on the call has just asked \
a question. Write what the user should say, from the material below and nothing else. The user glances at \
it while speaking: it must be readable in three seconds.{write_in}

Format, exactly:
SAY: one sentence of at most {say_words} plain spoken words, at most one number{said}. It starts with what \
is true and strong, never with "No", "Not", "Non", "Nessun" or "We don't", even when the question has a \
doubtful premise.
{slots}
Nothing more: {lines} No notes, no corrections. If you are unsure of a figure, leave it out rather than \
fix it in the text.

{how_lines}

Content:
- Every line answers THIS question. Leave out facts that are only near the topic.
- Every number says what it is and when ("€60,000 in Year 1"); a percentage says of what; a change says \
against what ("33% below plan"). Never "from €60,000" or a bare figure.
- A share names the amount it is a share of exactly as the material defines it, with its period ("of the \
€1.4m of the round used in the first 30 months"). Check which total the material divides: it may be neither \
the whole round nor the total spending.
- Say the plan's own labels (module names, scenario names, thresholds) in plain words. Keep the terms the \
listener uses in their own job. In another language, translate by meaning, not word for word ("delivery" \
in Italian is "avvio e assistenza clienti", not "consegna"). {language} Write numbers the way the \
answer's language does (in Italian "29.412" and "1,15 milioni", in English "29,412" and "1.15 million").
- Use only figures in the material, exactly as written. Never add, subtract or split figures yourself \
(no "the rest is 18%"): give the figures the material states. A forecast stays a forecast, an estimate an \
estimate; never call one a target.
{tone}
- "What if X happens": the SAY line gives the outcome plainly ("Even if 40% leave each year, we stay \
profitable."), the lines say what changes and what the plan does.
- Earlier questions and answers of this call come before the question: use them for follow-ups ("what do \
you mean by...") and stay consistent.
- If the material implies an answer (for example, it plans no further round), give it. If the question asks \
for something the material does not have, answer the part it has and make the last line "- Not in plan: \
<what is missing>" (in the answer's language: "- Non nel piano: ..."); it counts toward the maximum. If it has nothing relevant: "SAY: That is not in our plan yet." and at most one line \
with the closest fact.
{extra}
Examples (invented figures, only to show the form):
{examples}

Question: "Why can't a bigger rival just copy you?"
Good: "SAY: The combination is our edge, and we are building it fastest."
Bad: "SAY: No single feature is a moat, but the combination is." (opens with a negation)

Bad: "- CAC: €3,900 in Year 1, €6,100 in Year 2; €6,800 with founder time [Table 8]" (several numbers \
in one line). Bad: "SAY: 40% to S&M, the rest to delivery." (no base, labels the listener cannot decode)."""


def instructions(situation: str, style: Style) -> str:
    numbers = {0: "no numbers", 1: "at most one number"}.get(style.numbers, f"at most {style.numbers} numbers")
    lines = ("one line under the SAY line." if style.lines == 1 else
             f"at most {style.lines} lines under the SAY line; fewer is better.")
    form = FORMATS.get(style.format, FORMATS["talking"])
    slot = form["slot"].format(words=style.line_words, numbers=numbers) + (" [source]" if style.sources else "")
    slots = "\n".join([slot] * style.lines)
    text = ANSWER_INSTRUCTIONS.format(
        situation=situation, say_words=style.say_words,
        write_in=(f" Write the answer in {style.language}, whatever the language of the question or the material."
                  if style.language else ""), line_words=style.line_words, numbers=numbers,
        said=", said with confidence" if style.tone == "confident" else "",
        slots=slots, lines=lines, how_lines=form["how"], examples=form["examples"],
        language=f"Always answer in {style.language}." if style.language else "Answer in the language of the question.",
        tone=TONES.get(style.tone, TONES["confident"]),
        extra=(f"- The user's own instructions, followed unless they conflict with accuracy: {style.extra.strip()}\n"
               if style.extra.strip() else ""))
    if not style.sources:
        text = text.replace(" [source]", "")
        text = re.sub(r" \[(§|Table|Figure)[^\]]*\]", "", text)
    return text


FORMATS = {
    "talking": {
        "slot": "- A sentence the user can say as is, at most {words} words, {numbers}",
        "how": """How the lines read: the user reads them aloud and then talks around them, so each line is a \
short spoken sentence in the user's voice ("we", "our"), with a subject and a verb, one idea each, never a \
label followed by fragments ("IT: one connector, no port"). Read in order, the SAY line and the lines make one \
short spoken answer: the answer, then the proof, then what it means or what we do about it. A line may open \
with a short link that carries the thread ("Even at 19%...", "And if...", "That is why..."). Each line still \
stands on its own: the listener has not read the material.""",
        "examples": """Question: "Walk me through your go-to-market and your early CAC."
SAY: Founders sell first, then commission-only partners scale it cheaply.
- In Year 1 we founders close 12 of the 20 deals ourselves [§4.2]
- Partners then earn €2,000 only when a contract is signed [§4.2]
- That keeps our CAC at €3,900 per new customer in Year 1 [Table 8]

Question: "How will you use the money from the round?"
SAY: Of €2 million spent in two years, 40% builds sales.
- Most of that 40% goes on hiring our first sales team [Figure 6]
- Another 30% goes to product: engineers and outside development [Figure 6]
- The last 15% sets up and supports each new customer [Figure 6]

Question: "What if your enterprise pipeline doesn't convert?"
Good: "- We plan on a 24% win rate and stay profitable if it slips [§9.7]"
Bad: "- Pipeline: 24% win rate; at 19% Year 5 EBITDA falls 33% [§9.7]" (a label and fragments the user must \
connect while talking)""",
    },
    "facts": {
        "slot": "- Keyword: a phrase of at most {words} words, {numbers}",
        "how": """How the lines read: each line is one fact the user can quote, as "Keyword: phrase", the \
keyword naming what the fact is about. The lines are reference, not sentences to read aloud.""",
        "examples": """Question: "Walk me through your go-to-market and your early CAC."
SAY: Founders sell first, then commission-only partners scale it cheaply.
- Year 1: founders close 12 of 20 deals [§4.2]
- Partners: paid €2,000 only per signed contract [§4.2]
- CAC: €3,900 per new customer in Year 1 [Table 8]

Question: "How will you use the money from the round?"
SAY: Of €2 million spent in two years, 40% builds sales.
- Sales and marketing: 40%, mostly sales hires [Figure 6]
- Product: 30%, engineers and outside development [Figure 6]
- Onboarding and support: 15%, setting up and serving customers [Figure 6]""",
    },
    "script": {
        "slot": "- The next sentence of the answer, at most {words} words, {numbers}",
        "how": """How the lines read: the SAY line and the lines, read aloud in order, are the whole answer, \
like a short script the user can read almost word for word. Each line is the next sentence: it follows from \
the one before ("And...", "That is why...", "So..."), in the user's voice ("we", "our"), natural and spoken, \
never a label or a fragment.""",
        "examples": """Question: "Walk me through your go-to-market and your early CAC."
SAY: We sell it ourselves first, then partners scale it for us.
- In Year 1 we founders close 12 of the first 20 deals [§4.2]
- After that, partners take over and earn €2,000 only per signed contract [§4.2]
- So each new customer costs us €3,900 in Year 1 [Table 8]

Question: "How will you use the money from the round?"
SAY: The biggest share of the round builds our sales team.
- Of €2 million over two years, 40% goes to sales and marketing [Figure 6]
- The next 30% goes into the product and its engineers [Figure 6]
- And 15% makes sure every new customer is set up and supported [Figure 6]""",
    },
}


DETECT_INSTRUCTIONS = """You read lines from a live call. Decide whether the last line is a question or a \
request for information addressed to the user (it may lack a question mark). Small talk, greetings and \
rhetorical remarks are not questions. Reply with exactly YES or NO."""


@dataclass
class Usage:
    input: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output: int = 0

    def add(self, u: anthropic.types.Usage) -> None:
        self.input += u.input_tokens
        self.cache_write += u.cache_creation_input_tokens or 0
        self.cache_read += u.cache_read_input_tokens or 0
        self.output += u.output_tokens


@dataclass
class Answer:
    question: str
    text: str
    first_token: float  # seconds from request to first text
    total: float
    usage: Usage = field(default_factory=Usage)


def api_key() -> tuple[str | None, str]:
    """The Anthropic key and where it came from (see providers.py: environment first, then the Keychain)."""
    from .providers import api_key as provider_key
    return provider_key("anthropic")


def save_api_key(key: str | None) -> None:
    from .providers import save_api_key as save_provider_key
    save_provider_key("anthropic", key)


def client(key: str | None = None) -> anthropic.Anthropic:
    key = key or api_key()[0]
    if not key:
        raise RuntimeError("no Anthropic API key: add one on the setup screen")
    return anthropic.Anthropic(api_key=key)


class Copilot:
    def __init__(self, material: str, situation: str = "a meeting where the user is asked questions",
                 model: str = ANSWER_MODEL, api: anthropic.Anthropic | None = None, style: Style | None = None):
        self.api = api or client()
        self.model = model
        self.style = style or Style()
        # Sonnet 5.5 thinks by default; for a live answer, thinking off ("between_tools") at low effort.
        self.extra = ({"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}}
                      if model.startswith("claude-sonnet-5") else {})
        # Instructions first, material last and cached: one hour, because a call has quiet stretches
        # longer than the default five minutes.
        self.system = [
            {"type": "text", "text": instructions(situation, self.style)},
            {"type": "text", "text": material, "cache_control": {"type": "ephemeral", "ttl": "1h"}},
        ]

    def warm(self) -> Usage:
        """Write the material to the cache before the call, so the first question is fast."""
        usage = Usage()
        response = self.api.messages.create(
            model=self.model, max_tokens=1, system=self.system, **self.extra,
            messages=[{"role": "user", "content": "Reply OK."}],
        )
        usage.add(response.usage)
        return usage

    def is_question(self, line: str, before: str = "") -> bool:
        context = f"Previous line: {before}\n" if before else ""
        response = self.api.messages.create(
            model=DETECT_MODEL, max_tokens=3, system=DETECT_INSTRUCTIONS,
            messages=[{"role": "user", "content": f"{context}Last line: {line}"}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip().upper()
        return text.startswith("YES")

    history: list[tuple[str, str]] = []  # (question, answer) of this call, newest last, in memory only
    HISTORY_TURNS = 3

    think = False  # brief thinking before the answer: better first sentence, some latency (measured in evals)

    def answer(self, question: str) -> Iterator[str | Answer]:
        """Yield the answer text as it arrives, then the finished Answer with timings and usage."""
        started = time.perf_counter()
        first = None
        parts: list[str] = []
        messages = []
        for q, a in self.history[-self.HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": question})
        extra, limit = self.extra, 300 + 60 * self.style.lines
        if self.think and self.model.startswith("claude-sonnet-5"):
            extra, limit = {"thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}}, limit + 2000
        with self.api.messages.stream(
            model=self.model, max_tokens=limit, system=self.system, **extra, messages=messages,
        ) as stream:
            for text in stream.text_stream:
                if first is None:
                    first = time.perf_counter() - started
                parts.append(text)
                yield text
            final = stream.get_final_message()
        result = Answer(question, "".join(parts), first or 0.0, time.perf_counter() - started)
        result.usage.add(final.usage)
        yield result

    def remember(self, question: str, answer: str) -> None:
        """Keep an answered question for follow-ups (called only for lines that were real questions)."""
        self.history = (self.history + [(question, answer)])[-self.HISTORY_TURNS:]


# ── prepared answers and the combined check ──────────────────────────────────────────────────

CLASSIFY_INSTRUCTIONS = """You read lines from a live call. Classify the last line.
- NO: it asks for nothing. Greetings, thanks, small talk, agreement, comments, or the speaker talking about \
themselves.
- A number: it asks essentially the same thing as that prepared question below (same topic and same \
information wanted, even if worded differently).
- NEW: any other request for information, opinion or explanation, with or without a question mark: "how \
many...", "walk me through...", "tell me about...", "what if...", and short follow-ups that only name a \
topic or a figure ("and the margin in year three?"). If in doubt between NO and NEW, choose NEW.
Reply with exactly one token: NO, NEW, or a number.

Prepared questions:
{questions}"""


@dataclass(frozen=True)
class Prepared:
    question: str
    answer: str


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


class PreparedCopilot(Copilot):
    """A Copilot that also holds answers written before the call for the questions expected."""

    prepared: list[Prepared]

    def expected_questions(self, n: int = 25) -> list[str]:
        response = self.api.messages.create(
            model=self.model, max_tokens=1500, system=self.system, **self.extra,
            messages=[{"role": "user", "content":
                       f"List the {n} questions the other side of this call is most likely to ask, the hardest "
                       "and most decisive first. One question per line, no numbering, no other text."}],
        )
        return [q.strip("-• ").strip() for q in _text(response).splitlines() if q.strip()][:n]

    def prepare(self, questions: list[str], workers: int = 6) -> list[Prepared]:
        from concurrent.futures import ThreadPoolExecutor

        def one(question: str) -> Prepared:
            response = self.api.messages.create(
                model=self.model, max_tokens=300 + 60 * self.style.lines, system=self.system, **self.extra,
                messages=[{"role": "user", "content": question}],
            )
            return Prepared(question, _text(response))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            self.prepared = list(pool.map(one, questions))
        self._classify_system = CLASSIFY_INSTRUCTIONS.format(
            questions="\n".join(f"{i}. {p.question}" for i, p in enumerate(self.prepared, start=1)))
        return self.prepared

    def classify(self, line: str, before: str = "") -> str | Prepared | None:
        """None if not a question; a Prepared answer if one covers it; "NEW" otherwise."""
        system = getattr(self, "_classify_system", CLASSIFY_INSTRUCTIONS.format(questions="(none)"))
        context = f"Previous line: {before}\n" if before else ""
        response = self.api.messages.create(
            model=DETECT_MODEL, max_tokens=4, system=system,
            messages=[{"role": "user", "content": f"{context}Last line: {line}"}],
        )
        verdict = _text(response).upper().strip(". ")
        self.last_verdict = verdict  # raw reply, for diagnostics
        if verdict == "NO":
            return None
        if verdict.isdigit() and 1 <= int(verdict) <= len(getattr(self, "prepared", [])):
            return self.prepared[int(verdict) - 1]
        return "NEW"
