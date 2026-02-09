# MCP Configuration Guide

This document explains what's required to fully configure Playwright MCP (Model Context Protocol) integration for generating automation scripts in Phoenix.

## Current Status

**Manual Test Generation:** ✅ **Working** - Tests are generated locally without MCP  
**Automation Test Generation:** ⚠️ **Partial** - Structure exists but needs MCP integration

## What is MCP in Phoenix?

MCP (Model Context Protocol) is the intelligent layer that:
- Understands user stories and acceptance criteria
- Generates intelligent test cases (not just templates)
- Discovers stable locators from DOM
- Creates runnable Playwright scripts with proper selectors
- Analyzes test failures and suggests fixes

## What Needs to Be Configured

### Option 1: HTTP-Based MCP Server (Current Default)

If you have a Playwright MCP server running as an HTTP service:

#### 1. Configure MCP Server URL

**Via Environment Variable:**
```bash
export PHOENIX_MCP_SERVER_URL="http://localhost:8000"
```

**Via config.yaml:**
```yaml
mcp:
  server_url: "http://localhost:8000"
  timeout: 30
  retry_count: 3
```

#### 2. Start Your MCP Server

Your Playwright MCP server should:
- Accept HTTP POST requests
- Implement these endpoints:
  - `/generate_tests` - Generate test cases
  - `/discover_locators` - Discover element locators
  - `/analyze_failure` - Analyze test failures

**Expected Request Format:**
```json
POST /generate_tests
{
  "user_story": "As a user, I want to login",
  "application_url": "https://example.com/login",
  "acceptance_criteria": ["User can enter credentials", "User can click login"],
  "knowledge_context": "...",
  "test_type": "automation"
}
```

**Expected Response Format:**
```json
{
  "automation_tests": [
    {
      "name": "Test Login Flow",
      "description": "Test user login functionality",
      "test_steps": [
        "Navigate to login page",
        "Enter email",
        "Enter password",
        "Click login button",
        "Verify dashboard loads"
      ],
      "locators": [
        {
          "element": "Email input",
          "selector": "input[name='email']",
          "strategy": "name",
          "confidence": 0.95
        }
      ],
      "script_code": "def test_login(page):\n    page.goto('...')\n    ..."
    }
  ],
  "metadata": {
    "generated_at": "2024-01-01T00:00:00Z",
    "model_used": "gpt-4"
  }
}
```

#### 3. Implement MCP Client Methods

The following methods in `phoenix/mcp/client.py` need to be implemented:

**`generate_tests()`** - Currently returns placeholder:
```python
def generate_tests(self, user_story, acceptance_criteria, knowledge_context=None, **kwargs):
    # TODO: Replace with actual HTTP request to MCP server
    request_data = {
        "user_story": user_story,
        "application_url": kwargs.get("application_url"),
        "acceptance_criteria": acceptance_criteria,
        "knowledge_context": knowledge_context,
        "test_type": kwargs.get("test_type", "automation")
    }
    return self._make_request("/generate_tests", data=request_data)
```

**`discover_locators()`** - Currently returns placeholder:
```python
def discover_locators(self, page_url, element_name, dom_snapshot=None):
    # TODO: Replace with actual HTTP request
    request_data = {
        "page_url": page_url,
        "element_name": element_name,
        "dom_snapshot": dom_snapshot
    }
    return self._make_request("/discover_locators", data=request_data)
```

**`analyze_failure()`** - Currently returns placeholder:
```python
def analyze_failure(self, error_message, traceback=None, **kwargs):
    # TODO: Replace with actual HTTP request
    request_data = {
        "error_message": error_message,
        "traceback": traceback,
        **kwargs
    }
    return self._make_request("/analyze_failure", data=request_data)
```

---

### Option 2: Stdio-Based MCP Server (Recommended for Local)

If you have a local Playwright MCP that communicates via stdio (standard input/output):

#### 1. Update Configuration

**Add to `phoenix/sdk/config.py`:**
```python
class MCPConfig(BaseModel):
    """MCP server configuration"""
    # HTTP mode
    server_url: str = Field(default="http://localhost:8000", description="MCP server URL")
    
    # Stdio mode
    use_stdio: bool = Field(default=False, description="Use stdio instead of HTTP")
    mcp_command: str = Field(default="npx", description="Command to run MCP server")
    mcp_args: List[str] = Field(default_factory=lambda: ["-y", "@modelcontextprotocol/server-playwright"], description="MCP server arguments")
    
    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_count: int = Field(default=3, description="Number of retries on failure")
```

#### 2. Create Stdio MCP Client

Create `phoenix/mcp/stdio_client.py`:

```python
"""Stdio-based MCP client for local Playwright MCP"""

import json
import subprocess
from typing import Dict, Any, Optional, List
from phoenix.sdk.config import PhoenixConfig


class StdioMCPClient:
    """Client for communicating with Playwright MCP via stdio"""
    
    def __init__(self, config: PhoenixConfig):
        self.config = config.mcp
        self.process: Optional[subprocess.Popen] = None
        
    def _start_process(self):
        """Start MCP server process"""
        if not self.process:
            cmd = [self.config.mcp_command] + self.config.mcp_args
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
    
    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC request via stdio"""
        self._start_process()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json)
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        response = json.loads(response_line)
        
        if "error" in response:
            raise RuntimeError(f"MCP Error: {response['error']}")
        
        return response.get("result", {})
    
    def generate_tests(
        self,
        user_story: str,
        acceptance_criteria: List[str],
        application_url: Optional[str] = None,
        knowledge_context: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate tests via MCP"""
        params = {
            "user_story": user_story,
            "acceptance_criteria": acceptance_criteria,
            "application_url": application_url,
            "knowledge_context": knowledge_context,
            **kwargs
        }
        return self._send_request("tools/generate_tests", params)
    
    def discover_locators(
        self, page_url: str, element_name: str, dom_snapshot: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover locators via MCP"""
        params = {
            "page_url": page_url,
            "element_name": element_name,
            "dom_snapshot": dom_snapshot
        }
        return self._send_request("tools/discover_locators", params)
    
    def close(self):
        """Close MCP process"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
```

#### 3. Update Agent to Use MCP

Modify `phoenix/agents/test_generator.py`:

```python
def _generate_automation_tests(self, user_story, application_url, acceptance_criteria, knowledge_context, risk_level):
    """Generate automation test cases using MCP"""
    
    # Call MCP if available
    if self.mcp_client:
        try:
            mcp_result = self.mcp_client.generate_tests(
                user_story=user_story,
                acceptance_criteria=acceptance_criteria,
                application_url=application_url,
                knowledge_context=knowledge_context,
                test_type="automation"
            )
            
            # Parse MCP response
            automation_tests = mcp_result.get("automation_tests", [])
            if automation_tests:
                return automation_tests
        except Exception as e:
            # Fallback to local generation if MCP fails
            self.logger.warning(f"MCP generation failed, using fallback: {e}")
    
    # Fallback: Generate basic tests locally
    return [{
        "name": f"Automation Test: {user_story[:50]}...",
        "description": user_story,
        "script_template": "playwright",
        "test_steps": acceptance_criteria,
        "application_url": application_url,
        "risk_level": risk_level or "regression",
        "tags": ["automation", "generated"],
    }]
```

---

## Implementation Checklist

### Step 1: Choose Your MCP Setup
- [ ] **Option A:** Use existing HTTP MCP server
- [ ] **Option B:** Set up local stdio MCP server
- [ ] **Option C:** Build custom MCP server

### Step 2: Configure Phoenix
- [ ] Set `PHOENIX_MCP_SERVER_URL` (for HTTP) OR
- [ ] Set `PHOENIX_MCP_USE_STDIO=true` and `PHOENIX_MCP_COMMAND` (for stdio)

### Step 3: Implement MCP Client Methods
- [ ] Implement `MCPClient.generate_tests()` in `phoenix/mcp/client.py`
- [ ] Implement `MCPClient.discover_locators()` 
- [ ] Implement `MCPClient.analyze_failure()`
- [ ] OR implement `StdioMCPClient` if using stdio

### Step 4: Update Test Generator Agent
- [ ] Modify `TestGeneratorAgent._generate_automation_tests()` to call MCP
- [ ] Add error handling and fallback logic
- [ ] Parse MCP responses correctly

### Step 5: Test Integration
- [ ] Test with a simple user story
- [ ] Verify automation scripts are generated
- [ ] Check that scripts are runnable with pytest

---

## Quick Start: Using Existing MCP Server

If you already have a Playwright MCP server running:

```bash
# 1. Set MCP server URL
export PHOENIX_MCP_SERVER_URL="http://localhost:8000"

# 2. Update phoenix/mcp/client.py to implement generate_tests()
# (Replace the TODO placeholder with actual HTTP request)

# 3. Test generation
phoenix generate \
  --story "As a user, I want to login" \
  --url "https://example.com/login" \
  --criteria "User can enter credentials"
```

---

## Quick Start: Using Local Stdio MCP

If you want to use a local Playwright MCP via stdio:

```bash
# 1. Install Playwright MCP (if not already installed)
npm install -g @modelcontextprotocol/server-playwright

# 2. Set environment variables
export PHOENIX_MCP_USE_STDIO=true
export PHOENIX_MCP_COMMAND="npx"
export PHOENIX_MCP_ARGS='["-y", "@modelcontextprotocol/server-playwright"]'

# 3. Implement StdioMCPClient (see code above)

# 4. Update TestGeneratorAgent to use stdio client

# 5. Test generation
phoenix generate --story "..." --url "..." --criteria "..."
```

---

## What MCP Should Provide

Your MCP server (HTTP or stdio) should provide:

### 1. Test Generation
- **Input:** User story, acceptance criteria, application URL
- **Output:** Structured test cases with:
  - Test steps
  - Locators for each element
  - Runnable Playwright code
  - Assertions

### 2. Locator Discovery
- **Input:** Page URL, element description, DOM snapshot
- **Output:** Multiple locator strategies with confidence scores

### 3. Failure Analysis
- **Input:** Error message, traceback, test context
- **Output:** Failure reason and suggested fixes

---

## Troubleshooting

### Issue: "MCP server not responding"
- Check if MCP server is running: `curl http://localhost:8000/health`
- Verify `PHOENIX_MCP_SERVER_URL` is correct
- Check firewall/network settings

### Issue: "Automation tests not generated"
- Check MCP client is initialized in `AgentRegistry`
- Verify `test_type="automation"` is passed correctly
- Check logs for MCP errors

### Issue: "Generated scripts don't work"
- Verify MCP returns valid Playwright code
- Check that locators are correct
- Ensure application URL is accessible

---

## Next Steps

Once MCP is configured:
1. ✅ Automation scripts will be generated automatically
2. ✅ Locators will be discovered intelligently
3. ✅ Test failures will be analyzed automatically
4. ✅ Tests will be more reliable and maintainable

For questions or issues, check:
- `phoenix/mcp/client.py` - MCP client implementation
- `phoenix/agents/test_generator.py` - Test generation logic
- `phoenix/sdk/config.py` - Configuration options
