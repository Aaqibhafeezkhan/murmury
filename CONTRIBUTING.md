# Contributing to Murmury

Thanks for helping the elf. Issues, ideas and pull requests are all welcome.

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

## Good first contributions

- Try Murmury with a service other than Anthropic (OpenAI, Gemini, Grok, Groq, Mistral, OpenRouter) and
  report what works and what breaks.
- Add a local-model provider (Ollama or LM Studio) in `copilot/providers.py`.
- Improve how documents are read in `copilot/material.py` (Word, PowerPoint, Keynote).

By contributing you agree that your work is released under the [GPL-3.0](LICENSE) licence.
