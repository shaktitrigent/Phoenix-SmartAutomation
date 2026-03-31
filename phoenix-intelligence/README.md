# Phoenix Intelligence (LLM + MCP + Agents)

Phoenix Intelligence is the server-side reasoning layer. It hosts LLM integrations, Playwright MCP, and agent logic, and exposes a versioned API used by phoenix-core.

## Responsibilities
- LLM integrations (OpenAI / Gemini / Claude / local)
- Playwright MCP orchestration
- Agents for story analysis, test design, locator reasoning
- Prompt governance, caching, audit logging, masking
- Versioned HTTP/stdio API exposed to phoenix-core

## Constraints
- No client-side installation
- Centralized control and deployment
- No UI required at this stage

## API Contract
See `/contracts/openapi.yaml` for the current versioned API schema.

## Knowledge Base

Structured knowledge under `services/knowledge/` is used by agents to generate standard, consistent test scripts. In addition to test patterns, locator strategies, and best practices, Playwright-specific rules live under:

```
services/knowledge/
  playwright/
    locator_rules.md   # Locator priority, strict mode, anti-patterns
    assertions.md     # expect(), URL regex, visibility, form assertions
    waiting_rules.md  # Auto-waiting, dialogs, no fixed sleeps
    security_rules.md # No secrets, test data, temp files, cleanup
```

The Test Generator and Locator Expert agents receive this Playwright context so generated scripts follow these standards.

## Local Development (Placeholder)

```bash
cd phoenix-intelligence
# Start API service (to be implemented)
# python -m api.server
```
