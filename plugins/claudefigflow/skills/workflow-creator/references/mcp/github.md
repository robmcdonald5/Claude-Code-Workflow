# GitHub MCP Dunder Arguments Reference

This document lists all available dunder format arguments for GitHub MCP tools.

## Pull Request Reviews

### `mcp__github__add_comment_to_pending_review`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__path__`
- `__body__`
- `__subjectType__`
- `__line__`
- `__side__`
- `__startLine__`
- `__startSide__`

### `mcp__github__create_pending_pull_request_review`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__commitID__`

### `mcp__github__create_and_submit_pull_request_review`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__body__`
- `__event__`
- `__commitID__`

### `mcp__github__delete_pending_pull_request_review`
- `__owner__`
- `__repo__`
- `__pullNumber__`

### `mcp__github__submit_pending_pull_request_review`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__event__`
- `__body__`

### `mcp__github__request_copilot_review`
- `__owner__`
- `__repo__`
- `__pullNumber__`

## Issues

### `mcp__github__add_issue_comment`
- `__owner__`
- `__repo__`
- `__issue_number__`
- `__body__`

### `mcp__github__create_issue`
- `__owner__`
- `__repo__`
- `__title__`
- `__body__`
- `__assignees__`
- `__labels__`
- `__milestone__`
- `__type__`

### `mcp__github__get_issue`
- `__owner__`
- `__repo__`
- `__issue_number__`

### `mcp__github__get_issue_comments`
- `__owner__`
- `__repo__`
- `__issue_number__`
- `__page__`
- `__perPage__`

### `mcp__github__list_issues`
- `__owner__`
- `__repo__`
- `__after__`
- `__direction__`
- `__labels__`
- `__orderBy__`
- `__perPage__`
- `__since__`
- `__state__`

### `mcp__github__update_issue`
- `__owner__`
- `__repo__`
- `__issue_number__`
- `__title__`
- `__body__`
- `__assignees__`
- `__labels__`
- `__milestone__`
- `__state__`
- `__type__`

### `mcp__github__assign_copilot_to_issue`
- `__owner__`
- `__repo__`
- `__issueNumber__`

### `mcp__github__list_issue_types`
- `__owner__`

## Sub-Issues

### `mcp__github__add_sub_issue`
- `__owner__`
- `__repo__`
- `__issue_number__`
- `__sub_issue_id__`
- `__replace_parent__`

### `mcp__github__remove_sub_issue`
- `__owner__`
- `__repo__`
- `__issue_number__`
- `__sub_issue_id__`

### `mcp__github__list_sub_issues`
- `__owner__`
- `__repo__`
- `__issue_number__`
- `__page__`
- `__per_page__`

### `mcp__github__reprioritize_sub_issue`
- `__owner__`
- `__repo__`
- `__issue_number__`
- `__sub_issue_id__`
- `__after_id__`
- `__before_id__`

## Pull Requests

### `mcp__github__create_pull_request`
- `__owner__`
- `__repo__`
- `__title__`
- `__head__`
- `__base__`
- `__body__`
- `__draft__`
- `__maintainer_can_modify__`

### `mcp__github__create_pull_request_with_copilot`
- `__owner__`
- `__repo__`
- `__problem_statement__`
- `__title__`
- `__base_ref__`

### `mcp__github__get_pull_request`
- `__owner__`
- `__repo__`
- `__pullNumber__`

### `mcp__github__get_pull_request_comments`
- `__owner__`
- `__repo__`
- `__pullNumber__`

### `mcp__github__get_pull_request_diff`
- `__owner__`
- `__repo__`
- `__pullNumber__`

### `mcp__github__get_pull_request_files`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__page__`
- `__perPage__`

### `mcp__github__get_pull_request_reviews`
- `__owner__`
- `__repo__`
- `__pullNumber__`

### `mcp__github__get_pull_request_status`
- `__owner__`
- `__repo__`
- `__pullNumber__`

### `mcp__github__list_pull_requests`
- `__owner__`
- `__repo__`
- `__base__`
- `__direction__`
- `__head__`
- `__page__`
- `__perPage__`
- `__sort__`
- `__state__`

### `mcp__github__merge_pull_request`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__commit_message__`
- `__commit_title__`
- `__merge_method__`

### `mcp__github__update_pull_request`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__title__`
- `__body__`
- `__base__`
- `__draft__`
- `__maintainer_can_modify__`
- `__reviewers__`
- `__state__`

### `mcp__github__update_pull_request_branch`
- `__owner__`
- `__repo__`
- `__pullNumber__`
- `__expectedHeadSha__`

## Repository Management

### `mcp__github__create_repository`
- `__name__`
- `__description__`
- `__private__`
- `__autoInit__`

### `mcp__github__fork_repository`
- `__owner__`
- `__repo__`
- `__organization__`

### `mcp__github__create_branch`
- `__owner__`
- `__repo__`
- `__branch__`
- `__from_branch__`

### `mcp__github__list_branches`
- `__owner__`
- `__repo__`
- `__page__`
- `__perPage__`

## File Operations

### `mcp__github__get_file_contents`
- `__owner__`
- `__repo__`
- `__path__`
- `__ref__`
- `__sha__`

### `mcp__github__create_or_update_file`
- `__owner__`
- `__repo__`
- `__path__`
- `__content__`
- `__message__`
- `__branch__`
- `__sha__`

### `mcp__github__delete_file`
- `__owner__`
- `__repo__`
- `__path__`
- `__message__`
- `__branch__`

### `mcp__github__push_files`
- `__owner__`
- `__repo__`
- `__branch__`
- `__files__`
- `__message__`

## Commits and Tags

### `mcp__github__get_commit`
- `__owner__`
- `__repo__`
- `__sha__`
- `__page__`
- `__perPage__`

### `mcp__github__list_commits`
- `__owner__`
- `__repo__`
- `__author__`
- `__page__`
- `__perPage__`
- `__sha__`

### `mcp__github__get_tag`
- `__owner__`
- `__repo__`
- `__tag__`

### `mcp__github__list_tags`
- `__owner__`
- `__repo__`
- `__page__`
- `__perPage__`

## Releases

### `mcp__github__get_latest_release`
- `__owner__`
- `__repo__`

### `mcp__github__list_releases`
- `__owner__`
- `__repo__`
- `__page__`
- `__perPage__`

## Workflows and Actions

### `mcp__github__cancel_workflow_run`
- `__owner__`
- `__repo__`
- `__run_id__`

### `mcp__github__get_workflow_run`
- `__owner__`
- `__repo__`
- `__run_id__`

### `mcp__github__get_workflow_run_logs`
- `__owner__`
- `__repo__`
- `__run_id__`

### `mcp__github__get_workflow_run_usage`
- `__owner__`
- `__repo__`
- `__run_id__`

### `mcp__github__delete_workflow_run_logs`
- `__owner__`
- `__repo__`
- `__run_id__`

### `mcp__github__list_workflow_jobs`
- `__owner__`
- `__repo__`
- `__run_id__`
- `__filter__`
- `__page__`
- `__perPage__`

### `mcp__github__list_workflow_run_artifacts`
- `__owner__`
- `__repo__`
- `__run_id__`
- `__page__`
- `__perPage__`

### `mcp__github__download_workflow_run_artifact`
- `__owner__`
- `__repo__`
- `__artifact_id__`

### `mcp__github__list_workflow_runs`
- `__owner__`
- `__repo__`
- `__workflow_id__`
- `__actor__`
- `__branch__`
- `__event__`
- `__page__`
- `__perPage__`
- `__status__`

### `mcp__github__list_workflows`
- `__owner__`
- `__repo__`
- `__page__`
- `__perPage__`

### `mcp__github__rerun_failed_jobs`
- `__owner__`
- `__repo__`
- `__run_id__`

### `mcp__github__rerun_workflow_run`
- `__owner__`
- `__repo__`
- `__run_id__`

### `mcp__github__run_workflow`
- `__owner__`
- `__repo__`
- `__workflow_id__`
- `__ref__`
- `__inputs__`

### `mcp__github__get_job_logs`
- `__owner__`
- `__repo__`
- `__job_id__`
- `__run_id__`
- `__failed_only__`
- `__return_content__`
- `__tail_lines__`

## Security Alerts

### `mcp__github__get_code_scanning_alert`
- `__owner__`
- `__repo__`
- `__alertNumber__`

### `mcp__github__list_code_scanning_alerts`
- `__owner__`
- `__repo__`
- `__ref__`
- `__severity__`
- `__state__`
- `__tool_name__`

### `mcp__github__get_dependabot_alert`
- `__owner__`
- `__repo__`
- `__alertNumber__`

### `mcp__github__list_dependabot_alerts`
- `__owner__`
- `__repo__`
- `__severity__`
- `__state__`

### `mcp__github__get_secret_scanning_alert`
- `__owner__`
- `__repo__`
- `__alertNumber__`

### `mcp__github__list_secret_scanning_alerts`
- `__owner__`
- `__repo__`
- `__resolution__`
- `__secret_type__`
- `__state__`

## Discussions

### `mcp__github__get_discussion`
- `__owner__`
- `__repo__`
- `__discussionNumber__`

### `mcp__github__get_discussion_comments`
- `__owner__`
- `__repo__`
- `__discussionNumber__`
- `__after__`
- `__perPage__`

### `mcp__github__list_discussion_categories`
- `__owner__`
- `__repo__`

### `mcp__github__list_discussions`
- `__owner__`
- `__repo__`
- `__after__`
- `__category__`
- `__direction__`
- `__orderBy__`
- `__perPage__`

## Gists

### `mcp__github__create_gist`
- `__filename__`
- `__content__`
- `__description__`
- `__public__`

### `mcp__github__update_gist`
- `__gist_id__`
- `__filename__`
- `__content__`
- `__description__`

### `mcp__github__list_gists`
- `__username__`
- `__page__`
- `__perPage__`
- `__since__`

## Teams

### `mcp__github__get_team_members`
- `__org__`
- `__team_slug__`

### `mcp__github__get_teams`
- `__user__`

## Notifications

### `mcp__github__list_notifications`
- `__before__`
- `__filter__`
- `__owner__`
- `__page__`
- `__perPage__`
- `__repo__`
- `__since__`

### `mcp__github__get_notification_details`
- `__notificationID__`

### `mcp__github__dismiss_notification`
- `__threadID__`
- `__state__`

### `mcp__github__manage_notification_subscription`
- `__notificationID__`
- `__action__`

### `mcp__github__manage_repository_notification_subscription`
- `__owner__`
- `__repo__`
- `__action__`

### `mcp__github__mark_all_notifications_read`
- `__lastReadAt__`
- `__owner__`
- `__repo__`

## Search

### `mcp__github__search_code`
- `__query__`
- `__order__`
- `__page__`
- `__perPage__`
- `__sort__`

### `mcp__github__search_issues`
- `__query__`
- `__order__`
- `__owner__`
- `__page__`
- `__perPage__`
- `__repo__`
- `__sort__`

### `mcp__github__search_orgs`
- `__query__`
- `__order__`
- `__page__`
- `__perPage__`
- `__sort__`

### `mcp__github__search_pull_requests`
- `__query__`
- `__order__`
- `__owner__`
- `__page__`
- `__perPage__`
- `__repo__`
- `__sort__`

### `mcp__github__search_repositories`
- `__query__`
- `__page__`
- `__perPage__`

### `mcp__github__search_users`
- `__query__`
- `__order__`
- `__page__`
- `__perPage__`
- `__sort__`

## User Information

### `mcp__github__get_me`
- No dunder arguments