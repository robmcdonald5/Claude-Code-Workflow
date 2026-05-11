# Semgrep MCP Dunder Arguments Reference

This document lists all available dunder format arguments for Semgrep MCP tools.

## Schema and Language Support

### `mcp__semgrep__semgrep_rule_schema`
- No dunder arguments

### `mcp__semgrep__get_supported_languages`
- No dunder arguments

## Code Scanning

### `mcp__semgrep__semgrep_scan`
- `__code_files__`
- `__config__`

### `mcp__semgrep__semgrep_scan_with_custom_rule`
- `__code_files__`
- `__rule__`

### `mcp__semgrep__security_check`
- `__code_files__`

## Code Analysis

### `mcp__semgrep__get_abstract_syntax_tree`
- `__code__`
- `__language__`

## Tool Descriptions

### `mcp__semgrep__semgrep_rule_schema`
**Purpose**: Get the schema for a Semgrep rule. Use this tool when you need to:
- get the schema required to write a Semgrep rule
- need to see what fields are available for a Semgrep rule
- verify what fields are available for a Semgrep rule
- verify the syntax for a Semgrep rule is correct

**Arguments**: None

### `mcp__semgrep__get_supported_languages`
**Purpose**: Returns a list of supported languages by Semgrep. Only use this tool if you are not sure what languages Semgrep supports.

**Arguments**: None

### `mcp__semgrep__semgrep_scan`
**Purpose**: Runs a Semgrep scan on provided code content and returns the findings in JSON format. Use this tool when you need to:
- scan code files for security vulnerabilities
- scan code files for other issues

**Arguments**:
- `__code_files__` (required, array): List of dictionaries with 'filename' and 'content' keys
- `__config__` (optional, string): Optional Semgrep configuration string (e.g. 'p/docker', 'p/xss', 'auto')

### `mcp__semgrep__semgrep_scan_with_custom_rule`
**Purpose**: Runs a Semgrep scan with a custom rule on provided code content and returns the findings in JSON format. Use this tool when you need to:
- scan code files for specific security vulnerability not covered by the default Semgrep rules
- scan code files for specific issue not covered by the default Semgrep rules

**Arguments**:
- `__code_files__` (required, array): List of dictionaries with 'filename' and 'content' keys
- `__rule__` (required, string): Semgrep YAML rule string

### `mcp__semgrep__security_check`
**Purpose**: Runs a fast security check on code and returns any issues found. Use this tool when you need to:
- scan code for security vulnerabilities
- verify that code is secure
- double check that code is secure before committing
- get a second opinion on code security

If there are no issues, you can be reasonably confident that the code is secure.

**Arguments**:
- `__code_files__` (required, array): List of dictionaries with 'filename' and 'content' keys

### `mcp__semgrep__get_abstract_syntax_tree`
**Purpose**: Returns the Abstract Syntax Tree (AST) for the provided code file in JSON format. Use this tool when you need to:
- get the Abstract Syntax Tree (AST) for the provided code file
- get the AST of a file
- understand the structure of the code in a more granular way
- see what a parser sees in the code

**Arguments**:
- `__code__` (required, string): The code to get the AST for
- `__language__` (required, string): The programming language of the code

## CodeFile Object Structure

For tools that use `__code_files__`, the array should contain objects with:
- `filename` (required, string): Relative path to the code file
- `content` (required, string): Content of the code file