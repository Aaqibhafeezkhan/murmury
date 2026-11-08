# Contributing to Murmury

Issues, ideas and pull requests are welcome. If Murmury helps you, a star on GitHub helps others find it.

## Run it from source

You need a Mac with Apple Silicon, macOS 13 or later, [uv](https://docs.astral.sh/uv/) and the Xcode command
line tools.

```bash
git clone https://github.com/GianlucaBave/murmury && cd murmury
swiftc -O audiotap/main.swift -o audiotap/audiotap -framework ScreenCaptureKit -framework AVFoundation -framework CoreMedia
uv run python -m copilot.app
```

The first start downloads the speech model (Whisper large-v3-turbo, about 1.6 GB) and macOS asks for screen
recording permission, which is how the app hears the call's audio.

## Where things live

| Path | What |
|---|---|
| `audiotap/main.swift` | system audio and mic capture (ScreenCaptureKit) |
| `copilot/listen.py` | local transcription (mlx-whisper) |
| `copilot/material.py` | PDF, Excel and text into one prompt block |
| `copilot/pipeline.py` | question check and answer orchestration |
| `copilot/answer.py` | Anthropic answers, answer style and formats |
| `copilot/openai_copilot.py` | every OpenAI-format service |
| `copilot/providers.py` | the AI services, keys, model lists |
| `copilot/setup.py`, `copilot/app.py` | setup window and floating answer window |
| `evals/run.py` | answer-quality bench |
| `scripts/check_hidden.py` | proves the window stays out of screen capture |

## Before you open a pull request

- Keep the change small and focused; one idea per pull request.
- If you touch the answer instructions, run the bench on your own cases and put the before and after scores
  in the pull request: `uv run python -m evals.run path/to/cases.json` (`evals/cases.example.json` shows the
  format; a run costs a few cents to a few tens of cents of API usage).
- If you touch the floating window, run `uv run python scripts/check_hidden.py` and say what it printed.
- Never commit API keys, your own documents or call transcripts.

## Where to start

- Issues labelled [good first issue](https://github.com/GianlucaBave/murmury/issues?q=is%3Aopen+label%3A%22good+first+issue%22)
  are small and say what "done" looks like. `level 1`, `level 2` and `level 3` tell you the size: small,
  moderate, substantial.
- No code needed: try Murmury with a service other than Anthropic (OpenAI, Gemini, Grok, Groq, Mistral,
  OpenRouter, Ollama, LM Studio) and report what works and what breaks in
  [#3](https://github.com/GianlucaBave/murmury/issues/3).
- Have an idea that isn't in the issues? Open an issue first, so we can agree on it before you write code.

## How to take an issue

1. Comment on the issue that you'd like to work on it. We assign it to you, usually within a day.
2. One issue at a time, please, so others get a chance too.
3. Open a pull request within a week, even a draft. If you need more time, say so in the issue; without news
   for a week, the issue opens up again.
4. Link the issue in the pull request ("Closes #11").

Taking part in Winter of Code Social? Nothing extra to do: we add the `wocs` and level labels to your pull
request before merging it.

## Using AI tools

AI-assisted contributions are welcome, as long as you understand the change, tested it, and can explain it
in the review. Pull requests that look mass-generated, don't run, or that the author can't explain are closed.

## Contributor License Agreement

On your first pull request, CLA Assistant asks you to sign a short [agreement](docs/CLA.md) with one click.
You keep the copyright of your work; the agreement also lets the project use it under other licences.
