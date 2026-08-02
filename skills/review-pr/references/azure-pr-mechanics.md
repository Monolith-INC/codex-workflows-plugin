# Azure PR Mechanics

Exact MCP calls for the `review-pr` skill when
`.codex-workflows/scm-provider.json` has `"provider": "azure_devops"`.
Load this file at the start of INGEST and ACT (Azure path).

Repo identity comes from settings (`repo`), not from re-parsing `origin`.
Remote detection belongs only to PHASE 0 SETUP when the settings file is
missing.

## Infer branch from git

```bash
git branch --show-current
# e.g. feature/auth-token-fix
```

`repositoryId` for every Azure MCP call = `repo` from
`.codex-workflows/scm-provider.json`.

## INGEST — Fetch PR metadata

```
mcp__azure-devops__repo_get_pull_request_by_id
  repositoryId: <repo from scm-provider.json>
  pullRequestId: <PR-number>       # argument passed to skill
```

Extract from response: `title`, `description`, `targetRefName` (target branch), `createdBy.displayName`.

## INGEST — Fetch review threads

```
mcp__azure-devops__repo_list_pull_request_threads
  repositoryId: <repo from scm-provider.json>
  pullRequestId: <PR-number>
```

Each thread has: `id`, `status` (`active` | `resolved` | `wontFix` | `byDesign` | `pending` | `closed`), `threadContext` (`filePath`, `rightFileStart.line`), `comments[]`.

**Skip** threads where `status` is `resolved` or `wontFix`. Process all others.

Root comment of each thread: `comments[0]` — extract `content` (comment text) and `author.displayName` (reviewer name).

## INGEST — Fetch PR diff

```
mcp__azure-devops__repo_get_pull_request_changes
  repositoryId: <repo from scm-provider.json>
  pullRequestId: <PR-number>
```

Returns list of changed items with `item.path` and `changeType`. Use to locate the relevant file when classifying a thread anchored to a specific file/line.

To read the actual file content at the PR's source branch for diff context, use:
```
Read(<file-path>)
```
(reads from the working tree, which is checked out on the PR branch)

## ACT — Post reply to thread (reject items only)

```
mcp__azure-devops__repo_reply_to_comment
  repositoryId: <repo from scm-provider.json>
  pullRequestId: <PR-number>
  threadId: <thread.id>
  content: <reason text>
```

**CRITICAL**: Do NOT call `repo_update_pull_request_thread` or any status-changing tool. Only `repo_reply_to_comment`. Thread status remains exactly as fetched.

## Known gotchas

- `targetRefName` includes the `refs/heads/` prefix — strip it for display (e.g. `refs/heads/main` → `main`).
- `threadContext` is null for general (non-file-anchored) comments — handle gracefully (display as `[general comment]` with no file/line).
- `wontFix` in the API is camelCase, not `won't fix` — match on both when filtering.
- If `repo_get_pull_request_changes` returns no items, proceed without diff context and note it in the classification reasoning.
- Do not re-parse `git remote get-url origin` during INGEST/ACT; that bypasses SETUP overrides.
