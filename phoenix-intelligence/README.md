# phoenix-intelligence

The AI server. Hosts the LLM integrations, agents, and prompt library. Runs as a FastAPI service on port 8001 and is called by `phoenix-core` over HTTP.

## Starting the server

```powershell
cd phoenix-intelligence

# Windows
.\start_server.ps1

# macOS / Linux
uvicorn api.server:app --port 8001 --reload
```

Health check: `curl http://localhost:8001/health`

Interactive API docs: `http://localhost:8001/docs`

## Agents

| Agent | File | What it does |
|---|---|---|
| `TestGeneratorAgent` | `services/agents/test_generator.py` | Generates manual test cases + Playwright scripts from a user story |
| `ScriptFixerAgent` | `services/agents/script_fixer.py` | Fixes a failing script using its exact error output |
| `LocatorExpertAgent` | `services/agents/locator_expert.py` | Discovers stable Playwright locators for UI elements |
| `FailureAnalyzerAgent` | `services/agents/failure_analyzer.py` | Classifies a test failure and suggests a targeted fix |

All agents follow the same pattern: try the LLM first, fall back to a deterministic heuristic if the LLM is unavailable or fails.

## Prompts

Versioned Markdown files under `prompts/`. Each agent loads the latest version automatically.

```
prompts/
├── manual_test_generator/1.0.md
├── automation_from_manual/1.0.md
├── script_fixer/1.0.md
├── locator_expert/1.0.md
└── failure_analyzer/1.0.md
```

To update a prompt: edit the `.md` file and restart the server. To version it: create a `2.0.md` alongside — the loader picks the highest version.

## Knowledge base

Drop any `.md` file under `services/knowledge/` and it is injected into the relevant agent's prompt on the next request. No restart needed.

```
services/knowledge/
├── playwright/
│   ├── locator_rules.md       # Locator priority, strict mode, anti-patterns
│   ├── assertions.md          # expect(), URL regex, visibility checks
│   ├── waiting_rules.md       # Auto-waiting, no fixed sleeps
│   └── security_rules.md      # No hardcoded credentials, env vars only
├── test_patterns/
│   ├── login_flow.md
│   └── crud_operations.md
├── best_practices/
│   └── test_design.md
└── domain_knowledge/
    └── orangehrm.md           # App-specific locators (used only when URL matches)
```

## Security rule

Credentials are **never hardcoded** in generated code or prompts. Generated scripts always use:

```python
os.environ["TEST_USERNAME"]
os.environ["TEST_PASSWORD"]
os.environ["APP_URL"]
```

## LLM providers

Set one of these environment variables before starting the server:

| Provider | Variable |
|---|---|
| Anthropic (default) | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` + `PHOENIX_LLM_PROVIDER=openai` |
| Google Gemini | `GOOGLE_API_KEY` + `PHOENIX_LLM_PROVIDER=gemini` |
| Ollama (local) | `PHOENIX_LLM_PROVIDER=ollama` + `OLLAMA_BASE_URL=http://localhost:11434` |
