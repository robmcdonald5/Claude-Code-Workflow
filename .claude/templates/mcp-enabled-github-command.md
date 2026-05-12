---
description: "Automate GitHub PR creation with analysis"
allowed-tools: mcp__github__create_pull_request, mcp__github__list_pull_requests, mcp__github__get_pull_request_diff, Bash(git log:*), Bash(git diff:*), Read, Write
---
## Context
- Current branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -10`
- Uncommitted changes: !`git status --short`

## Your task
Create a pull request for: $ARGUMENTS

Steps:
1. Analyze the changes using `git diff` to understand the scope.
2. Use `mcp__github__get_pull_request_diff` or `git diff` outputs to compile a summary of changes.
3. Invoke `mcp__github__create_pull_request` with parameters:
   - __owner__: [determine from repository context or git config]
   - __repo__: [determine from repository context]
   - __title__: [derive a concise title based on changes and $ARGUMENTS]
   - __head__: [current branch name]
   - __base__: [target branch, e.g. main]
   - __body__: [detailed description of changes, possibly using the diff summary]
4. After creating the PR, use `mcp__github__list_pull_requests` to verify it was created successfully (or check output from create).
5. Output the PR URL or number and a confirmation message.

*(This command automates the process of summarizing changes and creating a GitHub PR, including validation. It uses GitHub MCP tools, so ensure the GitHub MCP server is connected and authenticated via `/mcp`.)*
