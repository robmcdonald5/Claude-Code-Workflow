# shadcn-ui-svelte MCP Dunder Arguments Reference

This document lists all available dunder format arguments for shadcn-ui-svelte MCP tools.

## Component Management

### `mcp__shadcn-ui-svelte__get_component`
- `__componentName__`

### `mcp__shadcn-ui-svelte__get_component_demo`
- `__componentName__`

### `mcp__shadcn-ui-svelte__list_components`
- No dunder arguments

### `mcp__shadcn-ui-svelte__get_component_metadata`
- `__componentName__`

## Repository and Directory Management

### `mcp__shadcn-ui-svelte__get_directory_structure`
- `__branch__`
- `__owner__`
- `__path__`
- `__repo__`

## Blocks Management

### `mcp__shadcn-ui-svelte__get_block`
- `__blockName__`
- `__includeComponents__`

### `mcp__shadcn-ui-svelte__list_blocks`
- `__category__`

## Tool Descriptions

### `mcp__shadcn-ui-svelte__get_component`
**Purpose**: Get the source code for a specific shadcn/ui v4 component

**Arguments**:
- `__componentName__` (required, string): Name of the shadcn/ui component (e.g., "accordion", "button")

### `mcp__shadcn-ui-svelte__get_component_demo`
**Purpose**: Get demo code illustrating how a shadcn/ui v4 component should be used

**Arguments**:
- `__componentName__` (required, string): Name of the shadcn/ui component (e.g., "accordion", "button")

### `mcp__shadcn-ui-svelte__list_components`
**Purpose**: Get all available shadcn/ui v4 components

**Arguments**: None

### `mcp__shadcn-ui-svelte__get_component_metadata`
**Purpose**: Get metadata for a specific shadcn/ui v4 component

**Arguments**:
- `__componentName__` (required, string): Name of the shadcn/ui component (e.g., "accordion", "button")

### `mcp__shadcn-ui-svelte__get_directory_structure`
**Purpose**: Get the directory structure of the shadcn-ui v4 repository

**Arguments**:
- `__branch__` (optional, string): Branch name (default: "main")
- `__owner__` (optional, string): Repository owner (default: "shadcn-ui")
- `__path__` (optional, string): Path within the repository (default: v4 registry)
- `__repo__` (optional, string): Repository name (default: "ui")

### `mcp__shadcn-ui-svelte__get_block`
**Purpose**: Get source code for a specific shadcn/ui v4 block (e.g., calendar-01, dashboard-01)

**Arguments**:
- `__blockName__` (required, string): Name of the block (e.g., "calendar-01", "dashboard-01", "login-02")
- `__includeComponents__` (optional, boolean): Whether to include component files for complex blocks (default: true)

### `mcp__shadcn-ui-svelte__list_blocks`
**Purpose**: Get all available shadcn/ui v4 blocks with categorization

**Arguments**:
- `__category__` (optional, string): Filter by category (calendar, dashboard, login, sidebar, products)