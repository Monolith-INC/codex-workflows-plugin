# Report Format

Templates for PRESENT and PERSIST phases. Load this file at the start of each phase.

## Terminal output — PRESENT phase

```
PR #<n> — "<title>"
Branch: <branch> → <target>
<N> threads fetched · <S> skipped (resolved / won't fix / outdated) · <A> active

════════════════════════════════════════════════════════════
COMPLY (<comply-count>)
════════════════════════════════════════════════════════════
[<idx>] <file>:<line>  @<reviewer>
    <comment_text — truncated at 120 chars, append "…" if longer>
    ACTION: <action>

════════════════════════════════════════════════════════════
REJECT (<reject-count>)
════════════════════════════════════════════════════════════
[<idx>] <file>:<line>  @<reviewer>
    <comment_text — truncated at 120 chars, append "…" if longer>
    REASON: <reason>

────────────────────────────────────────────────────────────
Review the list above. Tell me which items to change before I proceed.
(e.g. "flip 3 to reject, reason: ...", "change action on 7 to ...", "skip 10")
```

Rules:
- Items are numbered `[1]` through `[N]` sequentially across both sections.
- `<file>` is the relative file path from the thread; `<line>` is the right-side start line.
- For general (non-file-anchored) comments: show `[general]` in place of `<file>:<line>`.
- If there are zero comply or zero reject items, omit that section entirely.

## Accepted user adjustments (PRESENT phase)

| User says | Effect |
|-----------|--------|
| "looks good" or "proceed" | Accept all as-is, move to ACT |
| "flip \<n\> to comply, action: \<text\>" | Set item n reaction=comply, action=text, reason=null |
| "flip \<n\> to reject, reason: \<text\>" | Set item n reaction=reject, reason=text, action=null |
| "change action on \<n\> to \<text\>" | Replace item n action text; reaction stays comply |
| "change reason on \<n\> to \<text\>" | Replace item n reason text; reaction stays reject |
| "skip \<n\>" | Mark item n as skipped; exclude from ACT |

After applying all adjustments, re-print the full updated list and ask "Confirmed?" before proceeding to ACT.

## ACT outcomes section (appended to terminal output after ACT)

```
════════════════════════════════════════════════════════════
ACT OUTCOMES
════════════════════════════════════════════════════════════
COMPLY
[<idx>] <file>:<line>  →  done | failed: <reason>

REJECT
[<idx>] <file>:<line>  →  posted | failed: <reason>

────────────────────────────────────────────────────────────
Outcome: complete | partial
```

- `complete`: every non-skipped item succeeded.
- `partial`: one or more failed (details in the failed lines above).

## Vault note — PERSIST phase

**Path:** `AI_Codex/Agent_Reports/YYYY-MM-DD-pr-review-<PR#>.md`

**Frontmatter:**
```yaml
---
date: YYYY-MM-DD
type: report
pr: <number>
repo: <repo from scm-provider.json>
scm_provider: github | azure_devops
branch: <active branch>
outcome: complete | partial
---
```

**Body:** paste the full confirmed classification table (from PRESENT) followed by the ACT outcomes section, both verbatim, inside a fenced code block.
