# GitHub PR Mechanics

Exact `gh` / `gh api` calls for the `review-pr` skill when
`.codex-workflows/scm-provider.json` has `"provider": "github"`.
Load this file at the start of INGEST and ACT (GitHub path).

Requires authenticated `gh` (`gh auth status` must succeed). Owner/repo
**always** come from `.codex-workflows/scm-provider.json` (`owner`, `repo`).
Do not fall back to cwd remote resolution.

## Infer branch from git

```bash
git branch --show-current
# e.g. feature/auth-token-fix
```

Repo identity for every `gh` / `gh api` call: `-R <owner>/<repo>` or
`repos/<owner>/<repo>/...` using settings values.

## INGEST — Fetch PR metadata

```bash
gh pr view <PR-number> -R <owner>/<repo> --json title,body,baseRefName,author,headRefName
```

Extract: `title`, `body` (description), `baseRefName` (target branch),
`author.login`, `headRefName` (source branch).

If this fails, STOP: `INGEST failed — could not fetch PR #<n>: <error>`.

## INGEST — Fetch review threads

Prefer GraphQL so resolved/outdated state is available:

```bash
gh api graphql -f query='
query($owner:String!, $repo:String!, $number:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 1) {
            nodes {
              databaseId
              body
              author { login }
              path
              line
              originalLine
            }
          }
        }
      }
    }
  }
}' -F owner=<owner> -F repo=<repo> -F number=<PR-number>
```

Map each thread node to ReviewThread:

| Field | Source |
|---|---|
| `thread_id` | root comment `databaseId` (use for reply `in_reply_to`) |
| `status` | `resolved` if `isResolved`; else `outdated` if `isOutdated`; else `active` |
| `file` | first comment `path` (null if absent) |
| `line` | first comment `line`, else `originalLine` (null if both absent) |
| `comment_text` | first comment `body` |
| `reviewer` | first comment `author.login` |

**Skip** threads where `isResolved` or `isOutdated` is true. Count skipped
separately. Process all other threads.

If GraphQL fails, fall back to REST review comments (no reliable resolve
flag — treat kept roots as active and note the limitation in INGEST summary):

```bash
gh api repos/<owner>/<repo>/pulls/<PR-number>/comments --paginate
```

**Root-only filter (required):** keep only comments where `in_reply_to_id`
is null/absent. Drop replies. Each remaining root is one ReviewThread;
`thread_id` = that comment's `id` (same id used later for `in_reply_to`).

Map REST root items: `id` → `thread_id`, `path` → `file`,
`line`/`original_line` → `line`, `body` → `comment_text`,
`user.login` → `reviewer`, `status` → `active`.

General PR conversation comments (issue comments) are out of scope for
file-anchored review classification unless they are the only feedback;
prefer review threads.

## INGEST — Fetch PR diff / changed files

```bash
gh pr diff <PR-number> -R <owner>/<repo> --name-only
```

Store the list of changed file paths. During CLASSIFY, read file content
from the working tree with `Read(<file-path>)`.

Optional full diff (when needed for context):

```bash
gh pr diff <PR-number> -R <owner>/<repo>
```

If `--name-only` fails, log a warning and continue — CLASSIFY notes
absence of diff context.

## ACT — Post reply to thread (reject items only)

Reply to the root review comment; do **not** resolve or dismiss the thread.

```bash
gh api repos/<owner>/<repo>/pulls/<PR-number>/comments \
  -f body="<reason text>" \
  -F in_reply_to=<thread_id>
```

`thread_id` is the root comment `databaseId` / REST `id` captured at INGEST.

**CRITICAL:** Do NOT call any endpoint that resolves or dismisses a
review thread (for example GraphQL `resolveReviewThread`, or UI
"Resolve conversation" equivalents). Reply only.

## Known gotchas

- `gh` must be authenticated for the repo's host (`gh auth status`).
- Always pass `-R <owner>/<repo>` (or path segments from settings) so
  overrides/forks/multi-remote checkouts cannot mix repos.
- `line` may be null on outdated or multi-line comments — display as
  `[general]` when both `file` and `line` are missing; if `file` exists
  without `line`, show `<file>` without a line number.
- GraphQL `reviewThreads` is paginated (`first: 100`). If `pageInfo` is
  needed later, extend; for this pass, 100 threads is the documented cap.
- REST `in_reply_to` must reference a **pull review comment** id, not an
  issue comment id.
- REST fallback without root filtering will classify replies as threads —
  never skip the `in_reply_to_id` null check.
