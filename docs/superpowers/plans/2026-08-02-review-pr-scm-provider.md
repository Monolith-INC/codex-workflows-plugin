# review-pr Dual SCM Provider Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extend `review-pr` with PHASE 0 SETUP writing project-local `.codex-workflows/scm-provider.json`, and GitHub `gh` transport alongside existing Azure DevOps MCP.

**Architecture:** Skill-owned SETUP + provider adapters via mechanics reference files. CLASSIFY/PRESENT/PERSIST unchanged. Settings are skill-agnostic SCM config under `.codex-workflows/`.

**Tech Stack:** Skill markdown, `gh` CLI / GitHub REST, Azure DevOps MCP (unchanged).

## Global Constraints

- Project-only writes: `<project-root>/.codex-workflows/scm-provider.json` only.
- Providers: `github` | `azure_devops`.
- No thread resolve/dismiss; reply-only on reject.
- No auto-commit.
- Unknown remotes fail closed at SETUP.
- Spec: `docs/superpowers/specs/2026-08-02-review-pr-scm-provider-design.md`

## File map

| File | Role |
|---|---|
| `skills/review-pr/references/github-pr-mechanics.md` | Create — exact `gh` commands |
| `skills/review-pr/SKILL.md` | Modify — SETUP + provider switch |
| `skills/review-pr/manifest.json` | Modify — description |
| `skills/review-pr/references/report-format.md` | Modify — optional `scm_provider` frontmatter |
| `commands/review-pr.md` | Modify — dual-provider description |
| `CHANGELOG.md` | Modify — entry |

---

### Task 1: github-pr-mechanics reference

**Files:**
- Create: `skills/review-pr/references/github-pr-mechanics.md`

- [x] Write exact INGEST/ACT `gh` commands, thread mapping, skip rules, gotchas
- [x] Commit

### Task 2: SKILL.md + manifest + command

**Files:**
- Modify: `skills/review-pr/SKILL.md`
- Modify: `skills/review-pr/manifest.json`
- Modify: `commands/review-pr.md`
- Modify: `skills/review-pr/references/report-format.md`

- [x] Add PHASE 0 SETUP; branch INGEST/ACT on `provider`
- [x] Keep CLASSIFY/PRESENT/PERSIST; widen thread_id notes
- [x] Update command + manifest descriptions; report-format `scm_provider`
- [x] Commit

### Task 3: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [x] Document dual-provider + `scm-provider.json`
- [x] Commit
