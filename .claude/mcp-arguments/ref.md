# Ref MCP Dunder Arguments Reference

This document lists all available dunder format arguments for Ref MCP tools.

## Documentation Search and Reading

### `mcp__Ref__ref_search_documentation`
- `__query__`

### `mcp__Ref__ref_read_url`
- `__url__`

## Tool Descriptions

### `mcp__Ref__ref_search_documentation`
**Purpose**: Search for documentation on the web or github as well from private resources like repos and pdfs. Use Ref 'ref_read_url' to read the content of a url.

**Arguments**:
- `__query__` (required, string): Query for documentation. Should include programming language and framework or library names. Searches public only docs by default, include ref_src=private to search a user's private docs.

### `mcp__Ref__ref_read_url`
**Purpose**: Read the content of a url as markdown. The entire exact URL from a Ref 'ref_search_documentation' result should be passed to this tool to read it.

**Arguments**:
- `__url__` (required, string): The URL of the webpage to read.