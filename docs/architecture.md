# Phoenix Smart Automation - Architecture

## Overview
`phoenix-smart-automation` is a monorepo with strict domain isolation between **phoenix-core** (client SDK/CLI), **phoenix-intelligence** (server-side AI/MCP), and **phoenix-usage** (generated project outputs).

## Design Goals
- Deterministic execution on client machines
- No AI/MCP dependencies in phoenix-core
- Centralized governance of LLM/MCP in phoenix-intelligence
- Versioned API contract in `/contracts`
- CI/CD friendly, Git friendly outputs

## Monorepo Layout

```
phoenix-smart-automation/
├── phoenix-core/                 # Client SDK + CLI (pip install phoenix-core)
├── phoenix-intelligence/         # Server-side LLM + MCP + agents
├── contracts/                    # Versioned API schemas
├── examples/                     # Sample consumer projects
├── docs/                         # Architecture + ADRs
└── README.md
```

## Layer Responsibilities

### Phoenix Core (Client)
- CLI: `phoenix init`, `phoenix generate`, `phoenix run`
- Input: user story, URL, acceptance criteria
- Output: manual tests, Playwright scripts, HTML reports
- Execution: pytest + Playwright (local only)
- Communication: HTTP/stdio to phoenix-intelligence
- **No AI/LLM/MCP code, no API keys**

### Phoenix Intelligence (Server)
- Hosts LLMs and Playwright MCP
- Agent reasoning (test design, locator discovery, synthesis)
- Prompt governance, caching, audit logs, cost control
- Exposes versioned API consumed by phoenix-core

### Phoenix Usage (Generated Project)
- Manual tests in Markdown
- Automation scripts in pytest + Playwright
- Execution results and HTML reports
- CI/CD compatible and AI-independent at runtime

## Core → Intelligence Contract
- Defined in `/contracts/openapi.yaml`
- Versioned endpoints (e.g., `/api/v1/tests/generate`)
- Supports test generation, locator discovery, failure analysis

## Thin-Slice Workflow
1. `phoenix init` → create workspace + config
2. `phoenix generate` → call intelligence, write tests
3. `phoenix run` → execute locally, generate reports

## ADRs
See `docs/adrs/` for architectural decisions.
