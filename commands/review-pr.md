---
name: review-pr
description: >
  Classify GitHub or Azure DevOps PR review threads, present a report for
  confirmation, apply comply edits, post rejection replies, and persist
  results to AI_Codex. First run writes .codex-workflows/scm-provider.json.
  Invoke with a PR number: /review-pr <number>.
disable-model-invocation: true
allowed-tools: >
  Read Write Edit Glob Grep Bash
  mcp__azure-devops__repo_get_pull_request_by_id
  mcp__azure-devops__repo_list_pull_request_threads
  mcp__azure-devops__repo_get_pull_request_changes
  mcp__azure-devops__repo_reply_to_comment
---

# review-pr

Classify PR review threads (GitHub via `gh`, or Azure DevOps via MCP) and
act on the results.

Follow the full workflow in `skills/review-pr/SKILL.md`. Load reference
files from `skills/review-pr/references/` as each phase requires them.
