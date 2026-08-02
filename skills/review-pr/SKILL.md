---
name: review-pr
description: >
  Retrieve pull request review threads (GitHub via gh, or Azure DevOps via MCP),
  classify each as comply or reject, present a consolidated report for user
  confirmation, apply code edits for comply items, post rejection replies
  without changing thread status, and persist results to the AI Codex vault.
  First run writes project-local .codex-workflows/scm-provider.json from origin.
  Invoke with a PR number: /review-pr <number>.
  Repo and branch are inferred from scm-provider settings and the active branch.
disable-model-invocation: true
allowed-tools: >
  Read Write Edit Glob Grep Bash
  mcp__azure-devops__repo_get_pull_request_by_id
  mcp__azure-devops__repo_list_pull_request_threads
  mcp__azure-devops__repo_get_pull_request_changes
  mcp__azure-devops__repo_reply_to_comment
---

# review-pr

Classify PR review threads and act on the results. Provider is selected from
project-local SCM settings. Load reference files as each phase needs them.

References (in `references/`):
- `azure-pr-mechanics.md` — Azure DevOps MCP calls and gotchas.
- `github-pr-mechanics.md` — GitHub `gh` / `gh api` calls and gotchas.
- `report-format.md` — terminal output template and vault note template.

---

## PHASE 0 — SETUP

Runs before INGEST on every invocation.

**Input:** PR number passed as the skill argument (e.g. `42`). If multiple
numbers given, process only the first and warn:
`"review-pr processes one PR per invocation."`.

**1. Resolve project root:**

```bash
git rev-parse --show-toplevel
```

Settings path (project-only — never `$HOME` or plugin cache):

```text
<project-root>/.codex-workflows/scm-provider.json
```

**2. If the settings file exists:**

Read and validate required fields: `provider`, `owner`, `repo`.
`provider` must be `github` or `azure_devops`.

If invalid, STOP with repair guidance (fix or delete the file and re-run).
Do **not** re-detect from remotes while a valid file exists.

**3. If the settings file is missing:**

Detect from `origin` only:

```bash
git remote get-url origin
```

| Remote pattern | `provider` |
|---|---|
| host contains `github.com` | `github` |
| host contains `dev.azure.com`, `visualstudio.com`, or `ssh.dev.azure.com` | `azure_devops` |
| anything else | STOP — unsupported remote; do not guess |

Parse `owner` / `repo` from the URL:

- GitHub HTTPS/SSH (`github.com/org/repo.git` or `git@github.com:org/repo.git`):
  `owner` = org/user segment; `repo` = last segment with `.git` stripped.
- Azure DevOps HTTPS (`dev.azure.com/{org}/{project}/_git/{repo}`):
  `owner` = `{project}`; `repo` = last segment with `.git` stripped.
- Azure DevOps SSH (`ssh.dev.azure.com:v3/{org}/{project}/{repo}`):
  `owner` = `{project}`; `repo` = last segment with `.git` stripped.
- Azure legacy (`{org}.visualstudio.com/...`): same rule — `owner` =
  project segment when present; `repo` = last path segment.

Create `<project-root>/.codex-workflows/` if needed. Write:

```json
{
  "provider": "<github|azure_devops>",
  "detectedFrom": "origin",
  "owner": "<org-or-user>",
  "repo": "<repo-name>",
  "configuredAt": "<YYYY-MM-DD>"
}
```

Print:

```text
SETUP — configured scm-provider: <provider> (<owner>/<repo>) → .codex-workflows/scm-provider.json
```

**4. Load mechanics reference for INGEST/ACT:**

- `github` → read `references/github-pr-mechanics.md`
- `azure_devops` → read `references/azure-pr-mechanics.md`

Then proceed to PHASE 1.

---

## PHASE 1 — INGEST

Follow the loaded mechanics reference. Normalize every active thread into a
ReviewThread:

```text
{
  thread_id:    string | int
  file:         string | null
  line:         int | null
  reviewer:     string
  comment_text: string
  status:       string
  reaction:     "comply" | "reject"   // set in CLASSIFY
  reason:       string | null
  action:       string | null
}
```

Also record active branch:

```bash
git branch --show-current
```

### When `provider` is `azure_devops`

1. Call `mcp__azure-devops__repo_get_pull_request_by_id` with
   `repositoryId` = `repo` from settings, `pullRequestId` = PR number.
   Extract: `title`, `description`, `targetRefName` (strip `refs/heads/`),
   `createdBy.displayName`.
2. On failure, STOP: `"INGEST failed — could not fetch PR #<n>: <error>"`.
3. Call `mcp__azure-devops__repo_list_pull_request_threads`.
   Map fields per `azure-pr-mechanics.md`. Skip `resolved` / `wontFix`.
4. Call `mcp__azure-devops__repo_get_pull_request_changes` for changed paths.
   On failure, warn and continue.
5. For file context later, use `Read(<file-path>)` on the working tree.

### When `provider` is `github`

1. Run `gh pr view <n> -R <owner>/<repo> --json title,body,baseRefName,author,headRefName`
   per `github-pr-mechanics.md` (owner/repo from settings). Target branch = `baseRefName`.
2. On failure, STOP: `"INGEST failed — could not fetch PR #<n>: <error>"`.
3. Fetch review threads via GraphQL (preferred) or REST fallback; skip
   resolved/outdated; map fields per `github-pr-mechanics.md`.
4. Run `gh pr diff <n> -R <owner>/<repo> --name-only` for changed paths.
   On failure, warn and continue.
5. For file context later, use `Read(<file-path>)` on the working tree.

### INGEST summary (all providers)

```text
PR #<n> — "<title>"
Branch: <active-branch> → <target>
<N> threads fetched · <S> skipped · <A> active — proceeding to CLASSIFY
```

---

## PHASE 2 — CLASSIFY

For each active ReviewThread in order:

1. Read `comment_text` and `reviewer`.
2. If `file` is non-null and the file exists in the working tree, read the
   file with `Read(<file>)` and locate the region around `line` (±20 lines)
   for diff context.
3. Decide `comply` or `reject`:
   - **comply** — the reviewer's point is technically valid and the code
     should be changed. Set `action`: a concise description of the exact
     change needed, referencing file path and line number.
   - **reject** — the current implementation is correct or the reviewer
     lacks full context. Set `reason`: a paragraph (2–5 sentences) suitable
     for posting as a public reply — clear, respectful, technically
     grounded. No "you're wrong" framing.
4. Set `reaction`, and populate either `action` (comply) or `reason`
   (reject). Leave the other field null.

Proceed to PHASE 3 once all threads are classified.

---

## PHASE 3 — PRESENT

Read `references/report-format.md` for the exact terminal output template
before printing.

1. Print the full classification report using the template in
   `report-format.md`.
2. Wait for user input.
3. Apply any adjustments the user specifies — accepted verbs: flip /
   change action / change reason / skip (see full table in
   `report-format.md`).
4. Re-print the updated list.
5. Ask: `"Confirmed? (yes to proceed to ACT, or make further changes)"`
6. Wait for confirmation before proceeding.

Do not proceed to ACT until the user explicitly confirms.

---

## PHASE 4 — ACT

Re-read the provider mechanics reference before posting replies.

Execute confirmed items only. Process comply items first, then reject items.

**Comply items — code edits (all providers):**

For each comply item (not skipped):
1. Read the target file.
2. Apply the edit described in `action` using Edit or Write tools.
3. Do NOT commit. Changes land in the working tree.
4. Record outcome: `done` or `failed: <reason>`.

**Reject items — thread replies:**

For each reject item (not skipped):

- **azure_devops:** Call `mcp__azure-devops__repo_reply_to_comment` with
  `repositoryId` = settings `repo`, `pullRequestId`, `threadId` =
  `thread_id`, `content` = `reason`. Do NOT call any status-changing tool.
- **github:** Reply via `gh api` with `in_reply_to` = `thread_id` per
  `github-pr-mechanics.md`. Do NOT resolve or dismiss the conversation.

Record outcome: `posted` or `failed: <reason>`.

Print ACT outcomes to terminal using the template in `report-format.md`.

---

## PERSIST

Read `references/report-format.md` for the vault note template before writing.

Write the vault note to:

```text
AI_Codex/Agent_Reports/YYYY-MM-DD-pr-review-<PR#>.md
```

Use today's date (YYYY-MM-DD). Frontmatter and body follow the template in
`report-format.md`. Include `scm_provider` from settings.

Set `outcome`:
- `complete` if every non-skipped ACT item succeeded.
- `partial` if any item failed.

---

## Guardrails

- **Thread status immutability**: reply only; never resolve, dismiss, or
  update thread status (Azure or GitHub).
- **No automatic commits**: code edits land in the working tree; the user
  commits via `/commit-prep`.
- **Skip over reply errors**: if one reply fails to post, log the failure
  and continue with remaining items.
- **One PR per invocation**: warn and process only the first if multiple
  numbers given.
- **Skipped threads**: excluded from CLASSIFY, PRESENT display, and ACT.
  Never acted on.
- **Project-only settings**: write `.codex-workflows/scm-provider.json`
  only under the project root; never under `$HOME` or plugin cache.
- **Unknown remotes**: fail closed at SETUP.
