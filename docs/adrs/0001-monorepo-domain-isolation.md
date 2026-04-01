# ADR-0001: Monorepo with Domain Isolation

## Status
Accepted

## Context
We need rapid iteration while preserving strict separation between client SDK/CLI, intelligence services, and usage outputs.
The platform must scale to hundreds of engineers and comply with enterprise security and cost controls.

## Decision
Use a monorepo with three isolated domains:

- `phoenix-core/`: client SDK + CLI, deterministic execution only
- `phoenix-intelligence/`: LLM + MCP + agent services
- `phoenix-usage/`: generated project outputs

All cross-domain communication occurs through versioned API contracts in `/contracts`.

## Consequences
- Clear dependency boundaries and security posture
- Independent deployability of core and intelligence
- Faster iteration while preserving governance
- Requires contract discipline and compatibility testing
