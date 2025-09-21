# Zen — Multi‑Tool AI Agent

Zen is a developer‑friendly, multi‑intent AI agent that routes your prompt to the right capability:

- Web research with citations (Serper + CrewAI) via `tools/search.py`.
- Local chat over Ollama models via `tools/chat.py`.
- Secure Python code execution in a Docker sandbox via `tools/code_interpreter.py`.
- Visual browser automation and "computer use" via Playwright / browser-use in `tools/computer_use.py`.

The entrypoint is `main.py`, which classifies your query using `intents/classifier.py` and routes it via `intents/router.py`.

## Features

- Web: Source‑backed answers with a structured style, multilingual, time-aware formatting.
- Chat: Low‑latency local LLM chat through Ollama, with auto‑install/pull on Windows.
- Code: Docker‑isolated Python execution with AST validation, stdout truncation, and artifact collection.
- Computer: Browser automation (navigate, click, type, extract, screenshot, scroll, etc.) with annotated screenshots.

## Requirements

- Python 3.11+
- Windows 10/11 (project includes Windows‑friendly helpers); Linux/macOS should also work where supported by Docker/Playwright.
- Docker Desktop (for the Code Interpreter).
- Ollama (for local chat). The repo includes an automated installer for Windows.
- API keys:
  - SERPER_API_KEY (for web search results)
  - Optional: OPENAI_API_KEY (for intent classification with a cloud model; otherwise a heuristic is used)

## Install

1) Clone and create a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install Python dependencies:

- Fast path (scripted, shows a tiny loader):

```powershell
python utils/install_packages.py
```

- Or standard pip:

```powershell
pip install -r utils/requirements.txt
```

3) Playwright browsers (required for `computer_use`):

```powershell
playwright install chromium
```

4) Copy environment variables:

```powershell
copy .env.example .env
```

Then edit `.env` and set at minimum:

```
SERPER_API_KEY=your_serper_api_key
# If you want cloud intent classification:
OPENAI_API_KEY=your_openai_api_key
MODEL=gpt-5-mini
# Local model for chat via Ollama
OLLAMA_MODEL=mistral:7b
# Code sandbox limits (tweak as you like)
SANDBOX_DOCKER_IMAGE=python:3.11-slim
SANDBOX_TIMEOUT=10
SANDBOX_MEMORY=128m
SANDBOX_CPUS=0.5
SANDBOX_BASE_DIR=./sandbox_runs
SANDBOX_MAX_STDOUT=10000
CODE_INTERPRETER_UNSAFE=false
```

## Quick Start

Interactive mode:

```powershell
python main.py
```

One‑shot query:

```powershell
python main.py "Summarize latest PyTorch 2.5 release notes with sources"
```

You’ll see the router print which intent it selected and the result below it.

## Intents and Routing

Routing happens in `intents/classifier.py`:

- `web` — Research tasks that need fresh information or citations. Implemented by `tools/search.py` using Serper and CrewAI.
- `code` — Execute Python in a locked‑down Docker container, with AST checks and time/memory/CPU limits. Implemented by `tools/code_interpreter.py`.
- `computer` — Drive a real browser using Playwright (and optionally browser-use). Implemented by `tools/computer_use.py`.
- `chat` — General conversation using an Ollama model. Implemented by `tools/chat.py`.

If `OPENAI_API_KEY` is not provided or the SDK is unavailable, a simple heuristic decides between `code`, `computer`, and `chat` based on query keywords.

## Web Research (`tools/search.py`)

- Uses Serper to fetch results and formats a concise, skimmable answer with sources.
- The agent is built with CrewAI and a constrained system style (headings, short bullets, citations).
- Configure language hint by passing `lang_hint` to `run_zen_research(query, lang_hint)`.

Environment:

- `SERPER_API_KEY` must be set.

## Local Chat via Ollama (`tools/chat.py`)

- Talks to `http://localhost:11434` by default.
- Auto‑checks Ollama availability and model presence. On Windows, it will try to install Ollama via `winget` and then `ollama pull <model>` using `utils/install_ollama.py`.
- Change model with `OLLAMA_MODEL` in `.env` or by passing `model=` to `ChatTool` or `ChatAgent`.

Useful snippets:

```python
from tools.chat import simple_chat

print(simple_chat("Hey Zen, how are you?", model="mistral:7b"))
```

## Code Interpreter (`tools/code_interpreter.py`)

- Runs Python in Docker with network disabled, read‑only FS, memory/CPU caps, and a hard timeout.
- Performs AST‑based validation before execution.
- Copies artifacts out to `./output/` and zips the full workspace under `./sandbox_runs/`.

Environment knobs:

- `SANDBOX_DOCKER_IMAGE` (default `python:3.11-slim`)
- `SANDBOX_TIMEOUT` (seconds)
- `SANDBOX_MEMORY`, `SANDBOX_CPUS`
- `SANDBOX_BASE_DIR`, `SANDBOX_MAX_STDOUT`

Requirements:

- Docker Desktop running. On Windows, start it from the Start Menu before using the code interpreter.

## Computer Use (`tools/computer_use.py`)

- Playwright‑backed automation with helpers for `navigate`, `click`, `type`, `extract`, `screenshot`, `scroll`, `wait`, `hover`, `select`, `upload`, and custom `execute_script`.
- Takes annotated screenshots to help visualize actions.

Requirements:

- `playwright` Python package and a browser install: `playwright install chromium`.
- Optional `browser_use` integration if installed.

Example action (simplified):

```python
from tools.computer_use import EnhancedComputerUseTool

bot = EnhancedComputerUseTool()
res = bot._run(action="navigate", url="https://example.com")
print(res)
```

## Configuration Reference

See `.env.example` for a complete list. Key variables:

- `OPENAI_API_KEY`, `MODEL` — Optional, for LLM‑based intent classification.
- `SERPER_API_KEY` — Required for web search.
- `OLLAMA_MODEL` — Local chat model name (e.g., `mistral:7b`).
- Sandbox variables — Control Docker image and limits for code execution.

## Project Structure

```
.
├─ main.py
├─ intents/
│  ├─ classifier.py
│  └─ router.py
├─ tools/
│  ├─ chat.py
│  ├─ code_interpreter.py
│  ├─ computer_use.py
│  └─ search.py
├─ utils/
│  ├─ install_ollama.py
│  ├─ install_packages.py
│  ├─ loader.py
│  └─ requirements.txt
├─ .env.example
└─ README.md
```

## Troubleshooting

- Docker errors when running `code` intent
  - Ensure Docker Desktop is installed and running.
  - Verify your user can run `docker` without admin prompts.
  - Increase `SANDBOX_TIMEOUT` or resources if your code needs more time/CPU/RAM.

- Ollama cannot connect / model not found
  - Run `ollama serve` manually and then `ollama pull mistral:7b` (or your model).
  - On Windows, try: `python utils/install_ollama.py --model mistral:7b`.

- Playwright timeouts
  - Install browsers: `playwright install chromium`.
  - Some corporate proxies block downloads. Use an offline mirror or allowlist.

- No `web` results
  - Confirm `SERPER_API_KEY` is set and valid.

## Notes on Safety

- The code interpreter is sandboxed with Docker, AST validation, and resource limits to reduce risk. Treat it as best‑effort safety, not a guarantee. Don’t feed it secrets, and don’t mount sensitive host paths.
- The `computer_use` tool drives a real browser. Review selectors and URLs you automate, and prefer non‑privileged accounts.

## License

MIT
