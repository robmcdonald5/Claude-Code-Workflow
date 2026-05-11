---
description: "Automated web testing with Playwright"
allowed-tools: mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_type, mcp__playwright__browser_wait_for, Read, Write
---
## Your task
Perform automated browser testing on: $ARGUMENTS

Steps:
1. Navigate to the target URL using `mcp__playwright__browser_navigate`.
   - __url__: [the URL to test, likely passed via $ARGUMENTS]
2. Take a snapshot of the page with `mcp__playwright__browser_snapshot` (for baseline or debugging).
3. Interact with page elements:
   - Use `mcp__playwright__browser_click` with appropriate __element__ selectors (and optionally __ref__ if using references from snapshot).
   - Use `mcp__playwright__browser_type` for entering text into fields (specify __element__ and __text__).
4. Wait for any results or navigation using `mcp__playwright__browser_wait_for` as needed (e.g. waiting for a selector or network idle).
5. Capture a final screenshot or state if needed, and then summarize the actions performed and results.
6. (Optionally) Save results to a file like `test-results.md` or output relevant findings.

*(This command demonstrates a browser automation scenario. It navigates to a URL and performs interactions. Ensure that each MCP Playwright tool call includes necessary parameters like __element__ or __url__. The command should describe what it’s testing and output any notable observations.)*
