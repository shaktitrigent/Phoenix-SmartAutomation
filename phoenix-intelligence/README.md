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
| `TestGeneratorAgent` | `services/agents/test_generator.py` | Generates manual test cases + Playwright scripts from a user story; accepts `supporting_documents` and `domain_knowledge` |
| `ScriptFixerAgent` | `services/agents/script_fixer.py` | Fixes a failing script using its exact error output |
| `LocatorExpertAgent` | `services/agents/locator_expert.py` | Discovers stable Playwright locators for UI elements |
| `FailureAnalyzerAgent` | `services/agents/failure_analyzer.py` | Classifies a test failure and suggests a targeted fix |

All agents follow the same pattern: try the LLM first, fall back to a deterministic heuristic if the LLM is unavailable or fails.

## API models

### `SupportingDocument`

Represents a document attached to a user story (wireframe PDF, spec XLSX, schema JSON, etc.).

```python
class SupportingDocument(BaseModel):
    filename: str    # original filename, used in the prompt header
    format: str      # file extension without dot, e.g. "pdf", "xlsx"
    content: str     # extracted plain text (truncated to 8,000 chars per doc)
```

Sent via `TestGenerationRequest.supporting_documents: List[SupportingDocument]`.

### `TestGenerationRequest`

```python
class TestGenerationRequest(BaseModel):
    user_story: str
    application_url: str
    supporting_documents: List[SupportingDocument] = []   # story-specific docs
    domain_knowledge: str = ""                            # project-wide context
    generate_automation: bool = False
```

`domain_knowledge` is injected into every generation prompt. `supporting_documents` are injected only into the manual test generation prompt — they contain wireframes, specification PDFs, or data schemas specific to one user story.

## Prompts

Versioned Markdown files under `prompts/`. Each agent loads the latest version automatically.

```
prompts/
├── manual_test_generator/1.0.md      ← accepts supporting_documents section
├── automation_from_manual/2.0.md     ← DOM-grounded locators
├── script_fixer/1.0.md
├── locator_expert/1.0.md
├── failure_analyzer/1.0.md
├── test_name/1.0.md
└── test_quality_standards/1.0.md     ← injected into every generation pass
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
└── best_practices/
    └── test_design.md
```

> **Note:** `domain_knowledge/` is not part of the server's knowledge base. It is a folder inside the user's project (created by `phoenix init`) that is read by `phoenix-core` and sent to the server on each API request as the `domain_knowledge` field. The server injects it verbatim into the LLM prompt.

## Supporting documents vs domain knowledge

| | Supporting documents | Domain knowledge |
|---|---|---|
| **Source** | `user_stories/<story>/` folder (read by `phoenix-core`) | `domain_knowledge/` in the project root |
| **Scope** | One user story | Whole project |
| **Format** | Any: PDF, DOCX, XLSX, CSV, JSON, XML, TXT, MD | Markdown only |
| **Sent as** | `supporting_documents` list in request body | `domain_knowledge` string in request body |
| **Injected into** | Manual test generation prompt only | Every LLM prompt |

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
