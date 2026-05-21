# MCP Page Inspection

Phoenix uses [Playwright MCP](https://github.com/microsoft/playwright-mcp) (`@playwright/mcp`) as a **read-only page inspector**. When `phoenix automate` runs, the intelligence server can optionally navigate to the target URL and capture an accessibility snapshot — the live DOM tree rendered by the browser. This snapshot is injected into the LLM prompt so every locator is grounded in real DOM state.

---

## How it works

```
phoenix automate --url https://your-app.com
        │
        ▼
TestGeneratorAgent
        │
        ├─ MCPClient.inspect_page("https://your-app.com")
        │      │
        │      ▼
        │  @playwright/mcp (stdio)
        │      ├── browser_navigate(url)
        │      ├── browser_snapshot()    ← accessibility tree
        │      └── browser_close()
        │      returns: accessibility snapshot text (~3 000 chars)
        │
        ▼
LLM prompt includes snapshot
        │
        ▼
Generated script — every locator traced to a real DOM element
```

MCP is optional. If it is disabled or unavailable, the LLM generates locators from the manual test context alone and marks any element it cannot ground as `# UNGROUNDABLE`.

---

## Prerequisites

Node.js ≥ 18 must be installed. The MCP package is run on demand via `npx` — no global install required.

```powershell
node --version    # must be 18+
npx --version     # ships with Node.js
```

---

## Configuration

MCP is controlled by environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `PHOENIX_MCP_ENABLED` | `true` | Set `false` to skip page inspection |
| `PHOENIX_MCP_COMMAND` | `npx` | Command used to launch the MCP server |
| `PHOENIX_MCP_ARGS` | `-y @playwright/mcp@latest --headless` | Arguments passed to the command |

The settings are read by `phoenix-intelligence/services/config.py` (`MCPSettings`).

### Disable MCP (offline / CI environments)

```powershell
$env:PHOENIX_MCP_ENABLED = "false"
```

When disabled, locator generation falls back to structural inference from the manual test steps.

### Custom MCP arguments

```powershell
# Run headed (visible browser) for debugging
$env:PHOENIX_MCP_ARGS = "-y @playwright/mcp@latest"

# Pin to a specific MCP version
$env:PHOENIX_MCP_ARGS = "-y @playwright/mcp@0.0.29 --headless"
```

---

## What the snapshot looks like

The accessibility snapshot is a plain-text tree of visible roles, names, and attributes:

```
- navigation
  - link "Dashboard" [href="/dashboard"]
  - link "Leave" [href="/leave"]
- main
  - heading "Apply Leave" [level=1]
  - form
    - combobox "Leave Type"
    - textbox "From Date" [placeholder="yyyy-dd-mm"]
    - textbox "To Date"
    - textarea "Comments"
    - button "Apply"
```

The LLM uses this tree to pick the most stable locator for each element. Only elements visible in the snapshot get a locator; anything absent is flagged as UNGROUNDABLE.

---

## Troubleshooting

**"MCP page inspection failed"** in the server log:
- Check `node --version` is ≥ 18
- Check the app URL is reachable from the machine running the intelligence server
- Set `PHOENIX_MCP_ENABLED=false` to skip inspection and proceed without a snapshot

**Empty snapshot / snapshot too short:**
- The page may require authentication before meaningful content is visible
- Run `phoenix generate` first (generates manual tests) — MCP runs during `phoenix automate`

**Slow automation generation:**
- MCP launches a real browser per request; this adds ~5–15 seconds
- Set `PHOENIX_MCP_ENABLED=false` for repeated runs on the same page after the first snapshot is captured
