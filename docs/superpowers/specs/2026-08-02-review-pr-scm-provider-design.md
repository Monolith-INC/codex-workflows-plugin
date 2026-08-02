# review-pr — Dual SCM Provider Design Spec

**Date:** 2026-08-02  
**Status:** approved  
**Supersedes (in part):** `2026-06-25-review-pr-design.md` (Azure-only INGEST/ACT transport)  
**Preserves:** CLASSIFY, PRESENT, ACT (comply edits), PERSIST, and `report-format.md` semantics from the 2026-06-25 design

---

## Overview

Extend `review-pr` so the same skill works against **GitHub** and **Azure DevOps**. Provider selection is driven by a **project-only** settings file, created on first invocation via remote detection. CLASSIFY → PRESENT → ACT → PERSIST stay provider-agnostic.

---

## Goals

1. One command: `/review-pr <PR-number>`.
2. First call in a project configures SCM once and writes `.codex-workflows/scm-provider.json`.
3. Subsequent calls read that file; no re-detect while it exists.
4. GitHub uses `gh` / `gh api`; Azure DevOps keeps existing MCP tools.
5. All generated settings files are **project-local** (never `$HOME` or plugin cache).

## Non-goals

- GitLab, Bitbucket, or other forges in this pass.
- Auto-commit after comply edits.
- Resolving, dismissing, or closing review threads.
- Global / user-level SCM config.
- A separate `/review-pr-github` command.

---

## Project layout (consuming repo)

```text
your-project/
├── .codex-workflows/
│   └── scm-provider.json          # written on first /review-pr
├── AI_Codex/
│   └── Agent_Reports/
│       └── YYYY-MM-DD-pr-review-<n>.md
└── ...
```

## Plugin layout (upstream)

```text
codex-workflows-plugin/skills/review-pr/
├── SKILL.md                       # SETUP + provider switch + phases
├── manifest.json
└── references/
    ├── azure-pr-mechanics.md      # existing
    ├── github-pr-mechanics.md     # new
    └── report-format.md           # shared PRESENT / PERSIST
```

---

## Settings: `.codex-workflows/scm-provider.json`

Skill-agnostic name: this file describes the **repository SCM provider**, not the skill.

### Schema

```json
{
  "provider": "github" | "azure_devops",
  "detectedFrom": "origin",
  "owner": "<org-or-user>",
  "repo": "<repo-name>",
  "configuredAt": "YYYY-MM-DD"
}
```

| Field | Meaning |
|---|---|
| `provider` | Backend used for PR I/O |
| `detectedFrom` | Remote name used for detection (`origin`) |
| `owner` | Org or user parsed from the remote URL |
| `repo` | Repository name (`.git` suffix stripped) |
| `configuredAt` | ISO date of first successful setup |

### Detection rules (first run only)

Parse `git remote get-url origin`:

| Remote pattern | `provider` |
|---|---|
| host contains `github.com` | `github` |
| host contains `dev.azure.com`, `visualstudio.com`, or `ssh.dev.azure.com` | `azure_devops` |
| anything else | **STOP** — do not guess; report unsupported remote |

### Lifecycle

1. **File exists** → read it; use `provider` (and `owner` / `repo` as needed). Do not re-detect.
2. **File missing** → detect → create `.codex-workflows/` if needed → write `scm-provider.json` → print one-line setup summary → continue.
3. **Override** → user edits the file manually (or deletes it to force re-setup on next run).

### Project-only enforcement

- Write path is always `<project-root>/.codex-workflows/scm-provider.json`.
- Forbidden: `$HOME`, plugin install/cache directories, global agent settings for this purpose.

---

## Phases

### PHASE 0 — SETUP (new)

Runs before INGEST on every invocation.

1. Resolve project root (git top-level).
2. If `.codex-workflows/scm-provider.json` exists, load and validate required fields (`provider`, `owner`, `repo`). Invalid file → STOP with repair guidance.
3. Else run detection, write the file, report:

```text
SETUP — configured scm-provider: <provider> (<owner>/<repo>) → .codex-workflows/scm-provider.json
```

4. Load the matching mechanics reference:
   - `github` → `references/github-pr-mechanics.md`
   - `azure_devops` → `references/azure-pr-mechanics.md`

### PHASE 1 — INGEST

Same ReviewThread normalization as the 2026-06-25 design. Transport differs by provider.

**Shared summary line (unchanged shape):**

```text
PR #<n> — "<title>"
Branch: <active-branch> → <target>
<N> threads fetched · <S> skipped · <A> active — proceeding to CLASSIFY
```

#### Azure DevOps (unchanged)

- `repo_get_pull_request_by_id`
- `repo_list_pull_request_threads`
- `repo_get_pull_request_changes`
- Skip `resolved` / `wontFix`

#### GitHub (new)

- Metadata: `gh pr view <n> --json ...` (title, body, baseRefName, author, headRefName as needed)
- Threads: review comments (and conversation comments as applicable) via `gh api`, mapped to ReviewThread fields (`thread_id`, `file`, `line`, `comment_text`, `reviewer`, `status`)
- Skip resolved / outdated threads when GitHub exposes that state; count skipped separately
- Diff: `gh pr diff <n>` (and/or changed-file list); file context still via working-tree `Read`
- On metadata fetch failure → STOP: `INGEST failed — could not fetch PR #<n>: <error>`
- On diff failure → warn and continue (CLASSIFY notes missing diff context)

### PHASE 2 — CLASSIFY

Unchanged: comply vs reject; `action` or `reason`; optional ±20 line file context.

### PHASE 3 — PRESENT

Unchanged: `report-format.md` terminal template, user adjustments, explicit confirmation before ACT.

### PHASE 4 — ACT

- **Comply:** edit working tree only; no commit.
- **Reject:**
  - Azure: `repo_reply_to_comment` only; never change thread status.
  - GitHub: reply to the review comment thread via `gh api`; never resolve/dismiss the conversation.
- Skip over individual reply failures; continue remaining items.

### PERSIST

Unchanged path and templates:

```text
AI_Codex/Agent_Reports/YYYY-MM-DD-pr-review-<PR#>.md
```

Vault frontmatter may include `scm_provider: github | azure_devops` (additive; does not break existing consumers).

---

## Data model

ReviewThread remains:

```text
{
  thread_id:    string | int      // provider-native id (GitHub may be string)
  file:         string | null
  line:         int | null
  reviewer:     string
  comment_text: string
  status:       string
  reaction:     "comply" | "reject"
  reason:       string | null
  action:       string | null
}
```

`thread_id` widened to `string | int` so GitHub node/REST ids fit without a second model.

---

## Guardrails

- Thread / conversation status immutability (reply only).
- No automatic commits; user commits via `/commit-prep`.
- One PR per invocation.
- Skipped threads never enter CLASSIFY / PRESENT / ACT.
- Project-only settings writes.
- Unknown remotes fail closed at SETUP.

---

## Documentation / packaging updates

- Update `skills/review-pr/SKILL.md` description and phases for SETUP + dual provider.
- Update `manifest.json` description; GitHub path uses Shell/`gh` (not Azure MCP tools).
- Add `references/github-pr-mechanics.md` with exact `gh` / `gh api` commands and gotchas.
- CHANGELOG entry for dual-provider `review-pr` and `.codex-workflows/scm-provider.json`.
- Leave `2026-06-25-review-pr-design.md` in place; this spec is the additive dual-provider design.

---

## Success criteria

1. Fresh project with a GitHub `origin` and no `.codex-workflows/scm-provider.json`: first `/review-pr <n>` creates the file with `provider: "github"` and completes INGEST via `gh`.
2. Fresh project with an Azure DevOps `origin`: first run writes `provider: "azure_devops"` and uses existing MCP flow.
3. Second run in either project does not rewrite the file when it is valid.
4. Unsupported remote aborts at SETUP with a clear error.
5. Reject replies post without resolving threads on both providers.
6. No settings files written outside the project tree.
