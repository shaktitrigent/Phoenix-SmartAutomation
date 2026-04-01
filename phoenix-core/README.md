# Phoenix Core (SDK + CLI)

Phoenix Core is the client-side package installed by end users. It provides a deterministic SDK and CLI for test generation and execution. It **does not** contain any LLM, MCP, or agent logic.

## Responsibilities
- CLI: `phoenix init`, `phoenix generate`, `phoenix run`
- Accepts user story, URL, acceptance criteria
- Generates manual tests (Markdown) and automation scripts (pytest + Playwright)
- Executes tests locally and generates HTML reports
- Communicates with phoenix-intelligence via versioned API

## Constraints
- No LLM SDKs or API keys
- Deterministic execution
- Minimal dependencies
- Config-driven via `phoenix.yaml`

## Local Development

```bash
cd phoenix-core
python -m venv venv
./venv/Scripts/Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## CLI Usage

```bash
cd phoenix-core
./venv/Scripts/Activate.ps1
phoenix init --project-name my-project
phoenix generate --story "..." --url "..." --criteria "..."
phoenix run
```
