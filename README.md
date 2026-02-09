# Phoenix Enterprise QA Automation Platform

Phoenix is an enterprise-grade QA automation platform where **teams do not write automation code**. Users provide user stories, application URLs, and acceptance criteria, and Phoenix automatically generates both **manual test cases** and **runnable Playwright automation scripts**.

## What Phoenix Does

Phoenix transforms this:
```
User Story: "As a user, I want to login"
Application URL: "https://your-app.com/login"
Acceptance Criteria: ["User can enter email", "User can click login"]
```

Into this:
- **Manual test cases** (markdown files) for QA review
- **Runnable pytest + Playwright scripts** ready to execute
- **Test execution** with HTML reports

**No coding required** - Phoenix generates everything from your requirements.

## Key Features

- **No-Code Test Generation**: Generate tests from user stories and application URLs
- **Dual Output**: Creates both manual test cases (markdown) and automation scripts (Playwright)
- **Skill-Based Agents**: Specialized AI agents for test generation, locator discovery, and failure analysis
- **Knowledge Base**: Structured knowledge folders provide context to agents, reducing AI costs
- **Playwright MCP Integration**: Leverages Playwright MCP for intelligent test generation
- **Enterprise Ready**: SQLite for development, PostgreSQL for production
- **Simple CLI**: Easy-to-use command-line interface

## How It Works

### Architecture Flow

```
User Input (Story + URL + Criteria)
    ↓
Phoenix CLI/SDK
    ↓
Skill-Based Agents (Test Generator, Locator Expert, etc.)
    ↓
Knowledge Base (Test Patterns, Best Practices)
    ↓
Playwright MCP (Intelligent Generation)
    ↓
Generators (Manual + Automation)
    ↓
Output Files (Markdown + Python Scripts)
    ↓
Execution Engine (pytest + Playwright)
    ↓
HTML Reports
```

### Core Components

1. **SDK Client** (`phoenix/sdk/`) - Main entry point, orchestrates all components
2. **Agents** (`phoenix/agents/`) - Specialized AI agents:
   - `TestGeneratorAgent` - Generates test cases from user stories
   - `LocatorExpertAgent` - Discovers stable locators
   - `FailureAnalyzerAgent` - Analyzes test failures
3. **Knowledge Base** (`phoenix/knowledge/`) - Structured knowledge:
   - Test patterns (login flows, CRUD operations)
   - Locator strategies (best practices)
   - Domain knowledge (e-commerce, banking, etc.)
   - Best practices (test design principles)
4. **MCP Integration** (`phoenix/mcp/`) - Playwright MCP client for intelligent generation
5. **Generators** (`phoenix/generators/`) - Test generation:
   - `ManualTestGenerator` - Creates manual test markdown files
   - `AutomationTestGenerator` - Creates runnable Playwright scripts
6. **Execution** (`phoenix/execution/`) - Test execution engine (pytest integration)
7. **Storage** (`phoenix/storage/`) - Database (SQLite/PostgreSQL) and caching
8. **Reporting** (`phoenix/reporting/`) - HTML report generation

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Initialize Phoenix project
phoenix init --project-name my-project
```

## Quick Start

### CLI Usage (Recommended)

```bash
# 1. Initialize project
phoenix init --project-name demo

# 2. Generate tests (user story + application URL)
phoenix generate \
  --story "As a user, I want to login to the application" \
  --url "https://your-app.com/login" \
  --criteria "User can enter email and password" \
  --criteria "User can click login button" \
  --criteria "User is redirected to dashboard after login"

# Output:
# ✓ Generated 1 manual test(s)
# ✓ Generated 1 automation test(s)
#   Manual test saved: ./manual_tests/manual_test_001_*.md
#   Automation script saved: ./test_results/test_001_*.py

# 3. Run automation tests
pytest -v test_results/

# 4. View reports
# Reports are generated in ./reports/ after execution
```

### Python SDK Usage

```python
from phoenix import PhoenixClient

# Initialize client
client = PhoenixClient()
client.set_project("my-project")

# Generate tests
result = client.generate_tests(
    user_story="As a user, I want to login to the application",
    application_url="https://your-app.com/login",
    acceptance_criteria=[
        "User can enter email and password",
        "User can click login button",
        "User is redirected to dashboard after successful login"
    ],
    test_type="both"  # or "manual" or "automation"
)

# Manual tests saved to: ./manual_tests/
# Automation scripts saved to: ./test_results/

# Execute tests
execution_result = client.execute_tests()

# Get execution results
results = client.get_execution_results()
print(f"Report: {results['report_path']}")
```

## What Gets Generated

### Manual Test Cases (`./manual_tests/`)

Markdown files with structured test steps:

```markdown
Application URL: https://your-app.com/login

Test Case: Manual Test: As a user, I want to login...

Description: As a user, I want to login to the application

Steps:
  1. Navigate to https://your-app.com/login
  2. Step 1: User can enter email and password
  3. Step 2: User can click login button
  4. Step 3: User is redirected to dashboard after login

Expected Result: All acceptance criteria are met and the user story is fulfilled

Risk Level: REGRESSION
```

### Automation Scripts (`./test_results/`)

Runnable pytest + Playwright Python scripts:

```python
"""Generated Playwright UI Test
User Story: As a user, I want to login to the application
Application URL: https://your-app.com/login
"""

import pytest
from playwright.sync_api import Page, expect

def test_login(page: Page):
    """As a user, I want to login to the application"""
    # Navigate to application
    page.goto("https://your-app.com/login")
    page.wait_for_load_state('networkidle')
    
    # Step 1: User can enter email and password
    page.get_by_label("Email").fill("test@example.com")
    page.get_by_label("Password").fill("password123")
    
    # Step 2: User can click login button
    page.get_by_role("button", name="Login").click()
    
    # Step 3: User is redirected to dashboard after login
    # TODO: Add assertion for: User is redirected to dashboard after login
    
    # Assertions
    expect(page).to_have_url(containing="login"))
```

## CLI Commands

### Initialize Project
```bash
phoenix init --project-name my-project
```

### Generate Tests
```bash
# Generate both manual and automation tests
phoenix generate \
  --story "User story text" \
  --url "https://application-url.com" \
  --criteria "Acceptance criteria 1" \
  --criteria "Acceptance criteria 2"

# Generate only manual tests
phoenix generate --story "..." --url "..." --type manual

# Generate only automation tests
phoenix generate --story "..." --url "..." --type automation

# Specify risk level
phoenix generate --story "..." --url "..." --risk smoke
```

### Execute Tests
```bash
# Execute all automation tests in project
phoenix execute --project my-project

# Execute specific tests
phoenix execute --project my-project --test-ids 1 2 3

# Execute with specific browser
phoenix execute --project my-project --browser chromium
```

## Project Structure

### Block Diagram (Simplified)

```
                          ┌──────────────────────────┐
                          │        CLI / SDK         │
                          │   phoenix/cli, sdk/      │
                          └─────────────┬────────────┘
                                        │
                                        ▼
                          ┌──────────────────────────┐
                          │   Skill-Based Agents     │
                          │   phoenix/agents/        │
                          └─────────────┬────────────┘
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 ▼                      ▼                      ▼
       ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
       │   Knowledge Base │   │  MCP Integration │   │   Generators     │
       │ phoenix/knowledge│   │    phoenix/mcp   │   │ phoenix/generators│
       └─────────┬────────┘   └─────────┬────────┘   └─────────┬────────┘
                 │                      │                      │
                 └──────────────────────┼──────────────────────┘
                                        ▼
                          ┌──────────────────────────┐
                          │   Execution + Reporting  │
                          │ phoenix/execution,       │
                          │ phoenix/reporting        │
                          └─────────────┬────────────┘
                                        │
                                        ▼
                          ┌──────────────────────────┐
                          │   Storage + Cache        │
                          │ phoenix/storage          │
                          └──────────────────────────┘
```

### Folder Layout

```
phoenix/
├── phoenix/              # Core SDK package
│   ├── sdk/              # Main SDK module (PhoenixClient)
│   ├── agents/           # Skill-based agent system
│   │   ├── test_generator.py    # Test generation agent
│   │   ├── locator_expert.py    # Locator discovery agent
│   │   └── failure_analyzer.py  # Failure analysis agent
│   ├── knowledge/        # Knowledge base for agents
│   │   ├── test_patterns/       # Test pattern knowledge
│   │   ├── locator_strategies/  # Locator best practices
│   │   ├── domain_knowledge/    # Domain-specific knowledge
│   │   └── best_practices/      # QA best practices
│   ├── mcp/              # Playwright MCP integration
│   ├── generators/       # Test generation layer
│   │   ├── manual.py     # Manual test generator
│   │   └── automation.py # Automation script generator
│   ├── execution/        # Test execution engine
│   ├── storage/          # Data persistence (database + cache)
│   ├── reporting/        # HTML report generation
│   └── cli/              # Command-line interface
├── tests/                # Unit/integration tests
├── examples/             # Usage examples
└── README.md
```

## How Phoenix Works Internally

### 1. Test Generation Flow

```
User Story + URL + Criteria
    ↓
TestGeneratorAgent receives input
    ↓
Queries Knowledge Base for relevant patterns
    ↓
Calls Playwright MCP (if configured) for intelligent generation
    ↓
ManualTestGenerator creates markdown files
    ↓
AutomationTestGenerator creates Python scripts
    ↓
Files saved to disk + stored in database
```

### 2. Execution Flow

```
pytest discovers generated scripts
    ↓
Playwright runs tests in browser
    ↓
Results collected
    ↓
HTMLReporter generates reports
    ↓
Results stored in database
```

### 3. Knowledge Base System

Phoenix uses a structured knowledge base to provide context to agents:

- **Test Patterns**: Common patterns (login flows, CRUD operations)
- **Locator Strategies**: Best practices for stable locators
- **Domain Knowledge**: Domain-specific scenarios (e-commerce, banking)
- **Best Practices**: QA principles and guidelines

This reduces AI costs by providing structured context instead of relying solely on AI generation.

## Configuration

Phoenix uses environment variables or a `config.yaml` file:

```yaml
# config.yaml
database:
  url: "sqlite:///./phoenix.db"  # or PostgreSQL URL

mcp:
  server_url: "http://localhost:8000"  # MCP server URL (for HTTP mode)
  # OR use stdio mode:
  # use_stdio: true
  # mcp_command: "npx"
  # mcp_args: ["-y", "@modelcontextprotocol/server-playwright"]

project:
  default_project: "default"
  test_output_dir: "./test_results"
  report_output_dir: "./reports"
```

Or via environment variables:
```bash
export PHOENIX_DATABASE_URL="postgresql://user:pass@localhost/phoenix"
export PHOENIX_MCP_SERVER_URL="http://localhost:8000"  # For HTTP mode
# OR for stdio mode:
# export PHOENIX_MCP_USE_STDIO=true
# export PHOENIX_MCP_COMMAND="npx"
```

### MCP Configuration (Required for Automation Scripts)

**To generate automation scripts, you need to configure Playwright MCP integration.**

📖 **See [MCP Configuration Guide](docs/MCP_CONFIGURATION.md) for detailed setup instructions.**

**Quick Summary:**
- Manual tests work without MCP (generated locally)
- Automation scripts require MCP integration
- Two options: HTTP MCP server or local stdio MCP
- Once configured, automation scripts are generated automatically

## Database & Multi-Project Support

### Multiple Projects

Phoenix supports multiple projects in the same database:

```python
client.set_project("project-1")  # Switch between projects
client.set_project("project-2")
```

Each project's tests are isolated by `project_id` in the database.

### Team Collaboration

For team collaboration, use PostgreSQL:

```bash
export PHOENIX_DATABASE_URL="postgresql://user:pass@shared-server/phoenix"
```

All team members connect to the same database and can work on shared projects.

## Examples

See `examples/` directory for:
- `basic_usage.py` - Basic SDK usage
- `thin_slice_usage.py` - Simple user story + URL workflow

## Development

```bash
# Run tests
pytest

# Format code
black phoenix/

# Lint code
ruff check phoenix/
```

## License

MIT
