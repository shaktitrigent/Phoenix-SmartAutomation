# Contributing to Phoenix SmartAutomation

## Repository Layout

```
Phoenix-SmartAutomation/
├── shared/                  # Pydantic contracts — zero runtime deps beyond pydantic
├── phoenix-core/            # pip-installable SDK + CLI (no AI/LLM imports)
├── phoenix-intelligence/    # Hosted FastAPI server; all AI/LLM logic lives here
└── docs/                    # Architecture docs and guides
```

**Dependency rule**: `shared` ← `phoenix-core` ← user project.
`phoenix-intelligence` imports `shared` but **never** imports from `phoenix-core`.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | ≥ 3.11 |
| Node.js | ≥ 18 (for Playwright MCP page inspection) |
| pre-commit | ≥ 3.6 (optional but recommended) |

```powershell
pip install pre-commit
pre-commit install
```

---

## Development Setup

### 1. Clone and create a virtual environment

```powershell
git clone <repo-url>
cd Phoenix-SmartAutomation
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
```

### 2. Install packages in editable mode

```powershell
pip install -e shared/
pip install -e "phoenix-core/[dev]"
pip install -e "phoenix-intelligence/[dev]"
playwright install chromium
```

### 3. Configure the intelligence server

```powershell
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"

# Linux/macOS
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

---

## Running Tests

```powershell
# All tests
pytest

# Single package
cd phoenix-core && pytest tests/ -v
cd phoenix-intelligence && pytest tests/ -v

# With coverage
pytest --cov=phoenix --cov-report=term-missing
```

---

## Code Style

All code is formatted and linted with [Ruff](https://docs.astral.sh/ruff/).
Black-compatible formatting is enforced automatically via pre-commit hooks.

```powershell
# Manually run linting
ruff check . --fix
ruff format .

# Type checking
mypy phoenix-core/phoenix
mypy phoenix-intelligence/services
```

---

## Making Changes

### Branch naming

```
feat/<short-description>
fix/<issue-or-short-description>
refactor/<short-description>
docs/<short-description>
```

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(cli): add `phoenix report` command with Rich output
fix(intelligence): handle missing API key gracefully at startup
docs(contributing): add setup instructions for Windows
```

### Pull Request checklist

- [ ] All pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] Tests added/updated for new behaviour
- [ ] `shared/` models updated if the API contract changed
- [ ] README updated if user-facing behaviour changed
- [ ] No new direct imports of `anthropic` / LLM libraries in `phoenix-core`
- [ ] Prompt changes use a new version file (`prompts/<agent>/2.0.md`) not an edit to `1.0.md`

---

## Adding a New LLM Provider

1. Create `phoenix-intelligence/services/llm/providers/<provider>.py`
   implementing the `LLMProvider` protocol (see `services/llm/router.py`).
2. Register it in `services/llm/router.py` → `_PROVIDERS` dict.
3. Set `PHOENIX_LLM_PROVIDER=<provider>` and the matching `*_API_KEY` env var.
4. Add an integration test under `phoenix-intelligence/tests/`.

---

## Versioning Prompts

Prompt files live in `phoenix-intelligence/prompts/<agent>/`. The `PromptLoader` auto-selects the highest semantic version. To update a prompt:

1. Create a new file `<version+1>.md` — do **not** edit existing version files.
2. Add YAML front-matter with `version:` matching the filename.
3. The server picks up the new version on the next request (no restart needed).

---

## Reporting Issues

Please open a GitHub issue with:
- Phoenix version (`phoenix --version`)
- Python version (`python --version`)
- Minimal reproduction steps
- Full traceback (if applicable)
