# Playwright MCP Dunder Arguments Reference

This document lists all available dunder format arguments for Playwright MCP tools.

## Browser Management

### `mcp__playwright__browser_close`
- No dunder arguments

### `mcp__playwright__browser_resize`
- `__width__`
- `__height__`

### `mcp__playwright__browser_console_messages`
- No dunder arguments

### `mcp__playwright__browser_handle_dialog`
- `__accept__`
- `__promptText__`

### `mcp__playwright__browser_install`
- No dunder arguments

## Page Interaction

### `mcp__playwright__browser_evaluate`
- `__function__`
- `__element__`
- `__ref__`

### `mcp__playwright__browser_press_key`
- `__key__`

### `mcp__playwright__browser_type`
- `__element__`
- `__ref__`
- `__text__`
- `__slowly__`
- `__submit__`

### `mcp__playwright__browser_file_upload`
- `__paths__`

## Navigation

### `mcp__playwright__browser_navigate`
- `__url__`

### `mcp__playwright__browser_navigate_back`
- No dunder arguments

### `mcp__playwright__browser_navigate_forward`
- No dunder arguments

## Page Analysis

### `mcp__playwright__browser_network_requests`
- No dunder arguments

### `mcp__playwright__browser_take_screenshot`
- `__element__`
- `__ref__`
- `__filename__`
- `__fullPage__`
- `__type__`

### `mcp__playwright__browser_snapshot`
- No dunder arguments

## Element Interaction

### `mcp__playwright__browser_click`
- `__element__`
- `__ref__`
- `__button__`
- `__doubleClick__`

### `mcp__playwright__browser_drag`
- `__startElement__`
- `__startRef__`
- `__endElement__`
- `__endRef__`

### `mcp__playwright__browser_hover`
- `__element__`
- `__ref__`

### `mcp__playwright__browser_select_option`
- `__element__`
- `__ref__`
- `__values__`

## Tab Management

### `mcp__playwright__browser_tab_list`
- No dunder arguments

### `mcp__playwright__browser_tab_new`
- `__url__`

### `mcp__playwright__browser_tab_select`
- `__index__`

### `mcp__playwright__browser_tab_close`
- `__index__`

## Waiting

### `mcp__playwright__browser_wait_for`
- `__text__`
- `__textGone__`
- `__time__`