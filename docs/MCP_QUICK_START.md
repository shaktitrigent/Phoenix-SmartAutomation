# MCP Quick Start Guide

## What is MCP?

MCP (Model Context Protocol) is the intelligent layer that generates **smart automation scripts** (not just templates) with:
- Intelligent locator discovery
- Context-aware test generation
- Failure analysis

## Current Status

✅ **Manual Tests:** Working (generated locally)  
⚠️ **Automation Tests:** Need MCP integration

## Quick Setup (3 Steps)

### Step 1: Choose Your MCP Setup

**Option A: HTTP MCP Server (if you have one)**
```bash
export PHOENIX_MCP_SERVER_URL="http://localhost:8000"
```

**Option B: Local Stdio MCP (recommended)**
```bash
export PHOENIX_MCP_USE_STDIO=true
export PHOENIX_MCP_COMMAND="npx"
export PHOENIX_MCP_ARGS='["-y", "@modelcontextprotocol/server-playwright"]'
```

### Step 2: Implement MCP Client

**For HTTP:** Update `phoenix/mcp/client.py`:
```python
def generate_tests(self, user_story, acceptance_criteria, knowledge_context=None, **kwargs):
    request_data = {
        "user_story": user_story,
        "application_url": kwargs.get("application_url"),
        "acceptance_criteria": acceptance_criteria,
        "knowledge_context": knowledge_context,
        "test_type": kwargs.get("test_type", "automation")
    }
    return self._make_request("/generate_tests", data=request_data)
```

**For Stdio:** Create `phoenix/mcp/stdio_client.py` (see full guide)

### Step 3: Update Test Generator

Modify `phoenix/agents/test_generator.py`:
```python
def _generate_automation_tests(self, ...):
    if self.mcp_client:
        mcp_result = self.mcp_client.generate_tests(...)
        return mcp_result.get("automation_tests", [])
    # Fallback to local generation
```

## What You Get

Once configured, `phoenix generate` will create:
- ✅ Manual test cases (markdown)
- ✅ **Automation scripts** (pytest + Playwright) with intelligent locators

## Full Documentation

See **[MCP Configuration Guide](./MCP_CONFIGURATION.md)** for:
- Detailed setup instructions
- HTTP vs Stdio comparison
- Troubleshooting
- Implementation examples
