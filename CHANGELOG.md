# Changelog

All notable changes to `codex-workflows-plugin` are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_(nothing yet)_

## [0.5.16] - 2026-07-31

### Fixed
- Interactive `install.sh` preserves the caller's working directory after extracting the release tree, so project detection no longer targets the temp plugin extract.
- Wizard falls back to stdin/stdout when those are TTYs and `/dev/tty` is unavailable; no-TTY errors suggest a concrete `--dest` path.

## [0.5.15] - 2026-07-31

### Added
- Interactive `install.sh` wizard when `--dest` is omitted (`/dev/tty`), with project detection, post-install verification, and re-wire remediation.
- Cursor `.cursor/mcp.json` MCP mirror and Claude `.claude/settings.local.json` project MCP enablement during bootstrap.
- Codex/Cursor Azure DevOps interactive browser session env forwarding (`DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY`, `DBUS_SESSION_BUS_ADDRESS`, `XDG_RUNTIME_DIR`, `BROWSER`) when `@azure-devops/mcp` is already present with interactive auth.

### Fixed
- `wire()` / bootstrap restore `sys.path` and prior `scripts.*` modules after preferring the install runtime, so temporary install trees no longer break later imports (including the unittest suite).

### Changed
- Uninstall also cleans Cursor MCP orchestrator entries and Claude local MCP enablement for `agentic-orchestrator`.

## [0.5.9] - 2026-07-29

### Fixed
- Codex `PreToolUse` hooks no longer emit the unsupported `permissionDecision: "allow"` response for successful checks; allowed calls now exit silently, while denials use the current hook-specific schema.

## [0.5.8] - 2026-07-28

### Fixed
- `install.sh` standalone bootstrap: put `install_dir` on `sys.path` before importing `scripts.installer` modules so wiring no longer raises `ModuleNotFoundError: No module named 'scripts'`.
- Legacy `test_plugin` session fixtures now use current timestamps so allow-with-session cases do not fail the 8-hour gate after 20:00 local.

## [0.5.7] - 2026-07-25

### Added
- Session write gate continuity: open sessions (`next: null`) under `Agent_Sessions/` or `Projects/*/Agent_Sessions/` may continue when the same branch matches and the session is under 8 hours old; otherwise close and open a new session.
- `/skip-ledger` and `/resume-ledger` commands/skills: create or clear `{vault}/.codex_ledger_skip` to bypass session, ticket, YouTrack transcript, and protected-branch git guards for the session (vault destructive-delete protection stays on).
- Protected-branch git guard: block mutating git on `main`/`master`/`develop`/`unstable`; require creating a ticket branch (`feature/` / `bugfix/` / `techdebt/`) before commits and other mutations.
- Project-local installer discovery sync for Claude (`.claude/skills`, `.claude/commands`) and Antigravity (`.agents/skills`).

### Changed
- **BREAKING: global install removed.** Bootstrap/`install.sh` require `--dest`; runtime defaults to `<dest>/.codex-workflows`; home hook wiring and home plugin registration are gone. Skills/commands sync into project `.claude/` and `.agents/skills/`.
- Session denial messages now explain stale/mismatched open sessions instead of only requiring a same-day file.
- Plugin metadata bumped to `0.5.7` across Codex and Claude plugin manifests.

### Migration
```bash
# Project-only install (global install removed):
python3 -m scripts.installer.bootstrap --target all-agents --dest /path/to/project
# or
curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh \
  | bash -s -- --dest /path/to/project
```
Hooks and skills now live under the project (`.claude/`, `.agents/skills/`, `.agent/`). Runtime is `<dest>/.codex-workflows/`.

## [0.5.6] — 2026-07-25

### Changed
- **Markdown allowlist removed** from the policy engine and hook runtime. `.md` reads are no longer denied outside CLAUDE.md / `.agent/` / vault paths.
- Bootstrap **`wire()`** always deletes leftover `.claude/codex-workflow.config.json` allowlist companions when found.
- New bootstrap flags: `--purge-allowlist` (strip managed enforce hooks + remove allowlist configs) and `--scan-only` (report only).

### Removed
- `is_allowed_markdown` / `_is_markdown_denied` and the `markdown_allowed` event field.
- Tracked `.claude/codex-workflow.config.json` allowlist config from this repository.

### Migration
```bash
python3 -m scripts.installer.bootstrap --purge-allowlist --target all-agents --dest /path/to/project
```
Re-wires current (allowlist-free) hooks after stripping any leftover managed entries. Requires `--dest` (project-only install).

## [0.5.5] — 2026-07-09

### Added
- **Per-repo codex-workflow allowlist config** (`.claude/codex-workflow.config.json`): project-scoped config so the `codex-workflow@codex-workflow-marketplace` plugin's markdown allowlist covers this repo's own docs (`CHANGELOG.md`, `README.md`, `skills/**/*.md`, `docs/**`, etc.) when working inside the plugin itself.

### Changed
- Plugin metadata bumped to `0.5.5` across Codex and Claude plugin manifests.
- `.gitignore` now tracks `.claude/codex-workflow.config.json` via a negation rule while keeping the rest of `.claude/` local.

---

## [0.5.4] — 2026-07-09

### Fixed
- **Claude Code marketplace hook client detection** (`hooks/hooks.json`): the repo's own Claude Code plugin manifest called `codex_enforce_hook.py` directly, which defaults `WORKFLOW_HOOK_CLIENT` to `codex`. That made this repo's own Claude Code session parse and format policy decisions with the Codex adapter instead of the Claude adapter. Now routes through `${CLAUDE_PLUGIN_ROOT}/skills/codex_workflows/scripts/claude_enforce_hook.py`, which sets `WORKFLOW_HOOK_CLIENT=claude` before delegating to the shared runtime. Other hosts and installer-driven installs were unaffected — they already wired their own dedicated `*_enforce_hook.py` wrapper.

### Added
- **Per-repo codex-workflow allowlist config** (`.claude/codex-workflow.config.json`): adds a project-scoped config so the `codex-workflow@codex-workflow-marketplace` plugin's markdown allowlist covers this repo's own docs (`CHANGELOG.md`, `README.md`, `skills/**/*.md`, `docs/**`, etc.) when working inside the plugin itself. Without it, the plugin fell back to defaults that blocked reads on these files.

### Changed
- Plugin metadata bumped to `0.5.4` across Codex and Claude plugin manifests.
- Clarified in README and `SKILL.md` that `hooks/hooks.json` is the Claude Code marketplace hook manifest (not Codex's hook config, which the installer writes to `~/.gemini/config/hooks.json`).
- `.gitignore` now excludes `.claude/` but tracks `.claude/codex-workflow.config.json` via a negation rule.

---

## [0.5.3] — 2026-07-05

### Fixed
- **Private repository install path** (`install.sh`): the one-step installer now uses authenticated `gh release download` for the release zip when GitHub CLI is available, then falls back to unauthenticated Python downloads for public repositories. This fixes installs where `install.sh` was fetched with `gh` but the script failed with a GitHub `404` while downloading the release zip.

### Changed
- Plugin metadata bumped to `0.5.3` across Codex and Claude plugin manifests.

---

## [0.5.2] — 2026-07-05

### Added
- **One-step installer** (`install.sh`): supports `curl -fsSL https://github.com/theocarranza/codex-workflows-plugin/releases/latest/download/install.sh | bash`, downloads the latest GitHub release zip, extracts the bundled bootstrap script, and wires `--target all-agents` by default.
- `CODEX_WORKFLOWS_VERSION` support for pinning a release tag and `CODEX_WORKFLOWS_RELEASE_ZIP` support for local/offline test installs.
- Installer script tests covering default all-agents wiring, explicit target preservation, and uninstall argument passthrough.

### Changed
- README installation docs now lead with the one-step `curl | bash` flow instead of the broken `python3 bootstrap.py <zip>` example.
- Release packages now include `install.sh`.
- Plugin metadata bumped to `0.5.2` across Codex and Claude plugin manifests.

---

## [0.5.1] — 2026-07-05

### Added
- **Full uninstall cleanup** (`scripts/installer/uninstall.py`, `scripts/installer/bootstrap.py`): `python3 -m scripts.installer.bootstrap --uninstall` now removes managed host hook entries, Claude/Cursor/Antigravity plugin caches, the Claude local plugin registry entry, the Codex personal marketplace entry, and the installed `~/.codex-workflows/` runtime by default.
- `--dest`, `--keep-runtime`, and `--dry-run` support for uninstall cleanup. `--dest` also removes generated project-level hook configs and known `.agent/workflows` / `.agent/rules` assets while preserving unrelated project files.
- Temp-`HOME` uninstall integration coverage for full cleanup, project cleanup, runtime retention, and dry-run behavior.

### Changed
- README installation docs now include the primary uninstall command and clarify optional project cleanup/runtime-retention flags.
- Release metadata bumped to `0.5.1`.

### Fixed
- **Claude hook response schema** (`scripts/adapters/claude_adapter.py`): Claude decisions now emit `hookSpecificOutput.permissionDecision` / `permissionDecisionReason` for `PreToolUse` instead of the legacy top-level `decision` / `reason` shape.
- Claude payload parsing now recognizes `tool_input.file_path` for file-oriented tools.
- Claude plugin registration now copies runtime `scripts/` dependencies into the Claude plugin cache so cached plugin hooks can import their runtime modules.

---

## [0.5.0] — 2026-07-02

### Added
- **Cursor IDE support**: `cursor` installer target wires `~/.cursor/hooks.json`; `cursor_adapter.py` and `cursor_enforce_hook.py` normalize Cursor `preToolUse` payloads (Read/Write/Shell tool names).
- **`write-spec` skill**: Actor-Critic spec generation with templates (RFC, ADR, design doc, tech spec, SRS, implementation plan, bugfix spec, API contract), mistakes repository, and circuit breaker.
- **Generic reflection engine** (`scripts/artifact_reflection.py`): shared `ReflectionEngine`, `CriticProfile`, and vault-wide `_mistakes/mistakes.json` (legacy `Specs/_mistakes/` still read).
- **`resolve-ticket` Actor-Critic workflow**: resolution report at `<vault>/Specs/<slug>/resolution-report.md`, grounded on spec files and ticket ledger before archival.
- **`start-ticket` spec hook**: returns `write_spec_directive` when required spec kinds are missing under `<vault>/Specs/<slug>/`.
- **Spec/resolution runtimes**: `spec_runtime.py`, `resolution_runtime.py`, `spec_start_hook.py`, `resolve_ticket_hook.py`, and orchestrator handlers for `write-spec` and `resolve-ticket`.

### Changed
- **`start-ticket` / `resolve-ticket` manifests** bumped to v1.1.0 with input schemas and output signatures for orchestrator evaluation.
- **Hook runtime**: honors `CURSOR_PROJECT_DIR` for project root; recognizes Cursor write/shell tool names.

### Fixed
- **Bootstrap Codex registration**: `register_codex_plugin()` catches `OSError` when `~/.agents/plugins/marketplace.json` is not writable — install completes with a warning instead of exiting non-zero.

---

## [0.4.0] — 2026-07-02

### Added
- **Slash commands** (`commands/`): user-invocable Claude Code commands for `start-ticket`, `resolve-ticket`, `review-pr`, `commit-prep`, `automated-tests`, `repository-sync`, and `bootstrap`. Copied into the Claude plugin cache on bootstrap alongside skills.
- **Agentic orchestrator** (`scripts/orchestrator/`): event-sourced skill runner with schema validation, output evaluation, retry/circuit-breaker state machine, and an MCP stdio server (`agentic-orchestrator`). Invoked via `python3 -m scripts.orchestrator.mcp_server`.
- **Skill manifests** (`skills/*/manifest.json`): MCP-discoverable input schemas and output signatures for orchestrated skills.
- **`.claude-plugin/`** marketplace metadata for local Claude plugin distribution.
- **`scripts/validate_plugin.py`**: portable manifest validator used by CI (replaces the machine-specific Codex plugin-creator path).
- **Bootstrap orchestrator wiring**: `--dest` installs merge an `agentic-orchestrator` entry into the project's `.mcp.json` with absolute `PYTHONPATH` and `ORCHESTRATOR_SKILLS_DIR`.

### Changed
- **Installer/bootstrap**: copies `commands/` into the Claude plugin cache; warns when Claude plugin registration fails; Antigravity registration handles `OSError` without crashing bootstrap.
- **Release packager**: includes `commands/` and `.claude-plugin/` in the release archive.
- **`.mcp.json`**: adds `agentic-orchestrator` server entry for local development (skills dir resolved from module path when env is unset).

### Fixed
- **Orchestrator stream**: queued event dispatch prevents reentrancy drift when hooks emit nested events (e.g. `AuthorizationReceivedEvent`).
- **Orchestrator engine**: propagates `max_retries` to the reducer; guards retry loops with `retry_count < max_retries`; fails fast on identical retry output.
- **Orchestrator MCP server**: rejects non-dict JSON payloads; logs UI hooks to stderr to keep JSON-RPC stdout clean.
- **Orchestrator evaluator**: honors `output_signature.required`; validates `integer` type; excludes booleans from integer/number checks.
- **Manifest loader**: skips `manifest.json` files that parse to non-object JSON.
- **Reducer**: dependency resolution no longer crashes on missing task IDs.
- **`start-ticket` handler**: creates the active ledger file when a project root env var is set.
- **`review-pr` command**: thin delegate to `skills/review-pr/SKILL.md` (removes duplicated workflow body).

---

## [0.3.0] — 2026-06-25

### Added
- **`review-pr` skill** (`skills/review-pr/`): four-phase skill that retrieves Azure DevOps pull request review threads, classifies each comment as comply or reject, presents a structured report for user review, then acts on confirmed decisions — applying code edits for comply items and posting rejection replies for reject items. Thread status is never mutated; only a reply is added. Results are persisted to `AI_Codex/Agent_Reports/YYYY-MM-DD-pr-review-<PR#>.md`.
- **`.mcp.json`**: Azure DevOps MCP server config (`@azure-devops/mcp`, org `bhave-tecnologia-comportamental`) for local development of `review-pr`.

---

## [0.2.8] — 2026-06-23

### Added
- **Claude Code plugin registration** (`scripts/installer/bootstrap.py`): bootstrap now copies the plugin's `skills/` tree into `~/.claude/plugins/cache/local/codex-workflows-plugin/<version>/` and adds a `codex-workflows-plugin@local` entry to `~/.claude/plugins/installed_plugins.json`. The plugin now appears in Claude's plugin manager and all skills are discoverable in any Claude session after restarting. The `installPath` is placed inside the standard Claude cache directory — the same structure used by marketplace plugins — which is required for skills to load.
- `strip_managed_hooks(config, script_names)` in `bootstrap.py`: strips all hook entries whose command references any of this plugin's known hook scripts before re-wiring. Prevents stale entries (e.g. paths from previous temp directories or old install locations) from accumulating across bootstrap runs.

### Fixed
- **Hook deduplication** (`scripts/installer/merge.py`): `deep_merge` previously concatenated hook-group lists unconditionally, causing a new duplicate hook entry to be appended to the target config on every bootstrap run. Hook-group lists (arrays whose elements each contain a `"hooks"` key) are now deduplicated by command string — only the first occurrence of each unique command is kept. Existing configs with accumulated duplicates are cleaned on the next bootstrap run via `strip_managed_hooks`.

---

## [0.2.7] — 2026-06-21

### Added
- Standardized templates for issue/ticket creation (`feature-template.md`, `bug-template.md`, `task-template.md`) under `.agent/workflows/templates/`.
- Workflow guide `workflows-create-issue.md` under `.agent/workflows/` detailing the step-by-step issue creation, YouTrack MCP registration, and local ticket lifecycle file movements.
- Script harness `scripts/create_ticket.py` to scaffold local ticket drafts and generate YouTrack MCP payload.

### Changed
- Refactored `sync_shared_assets(dest_root)` in `scripts/installer/cli.py` to recursively copy subdirectories under `.agent/workflows/` (allowing `templates/` folder to sync to the target project).

---

## [0.2.6] — 2026-06-09

### Added
- `target_global_config_path(target)` in `scripts/installer/targets.py`: returns the machine-global hook config location for each supported host, encoding the knowledge gathered about each host's internals:
  - Claude Code → `~/.claude/settings.json`
  - Gemini CLI → `~/.gemini/settings.json`
  - Codex → `~/.gemini/config/hooks.json` (Codex uses the Gemini CLI config layer)
  - Antigravity → `<ide-install>/.agents/hooks.json` (IDE install dir auto-discovered from `~/Antigravity_IDE/`, `~/antigravity-ide/`, `/opt/…`)
- `bootstrap.py` global install mode: `--dest` is now optional. When omitted, `wire()` writes hooks directly to each host's global config location. No project path knowledge required from the user.

### Changed
- README Step 2 rewritten: primary example wires all agents globally (`--target all-agents` with no `--dest`); project-level wiring documented as Step 2b.
- Global Claude settings (`~/.claude/settings.json`) hook deduplicated and updated to reference `~/.codex-workflows/` instead of the project clone path.

---

## [0.2.5] — 2026-06-09

### Changed
- `bootstrap.py` now accepts `--target` and `--dest` to install and wire in a single command:
  `python3 bootstrap.py plugin.zip --target all-agents --dest /my/project`
- Added `--install-dir` flag to override the default install location (`~/.codex-workflows/`).
- Wire-only mode: if `~/.codex-workflows/` already exists and only `--target`/`--dest` are passed, the install step is skipped.

---

## [0.2.4] — 2026-06-09

### Added
- `scripts/installer/bootstrap.py`: one-time install script that copies the plugin runtime to `~/.codex-workflows/` from either a release zip or the source tree. Running the hook-wiring CLI from that stable location ensures hook commands reference `~/.codex-workflows/` rather than wherever the repo happens to be cloned.
- 10 new tests for `bootstrap.py` (source install, zip install, CLI, pycache exclusion, idempotent replace, and the key property: hook commands generated from the installed location point back to `~/.codex-workflows/`). Total: 85 tests.

### Changed
- README Installation section rewritten as a two-step flow: bootstrap once (Step 1), then wire each project (Step 2). Includes update instructions.

---

## [0.2.3] — 2026-06-09

### Fixed
- **Installer portability**: hook commands are now written as absolute paths to the plugin's own scripts directory, so the hook fires correctly from any `--dest` project regardless of working directory. Previously the relative path `python3 skills/codex_workflows/scripts/<host>_enforce_hook.py` would fail in any project that didn't contain the plugin's `skills/` folder.

---

## [0.2.2] — 2026-06-09

### Added
- Timer and Spent time verification to the pre-tool hook (`check_youtrack_state_in_transcript` in `ticket_runtime.py`):
  - Active tickets must have `Timer: "Start"` and `State: "In Progress"`.
  - Finished (Resolved/Closed) tickets must have `Timer: "Stop"`, `State: "Done"` or `"Fixed"`, and a non-empty `Spent time` value.
- **Git safety enforcement on ticket start** (`scripts/policy/git_utils.py` + `engine.py`):
  - Blocks starting a ticket if another ticket is already active in `Tickets/Active/`.
  - Blocks starting a ticket while checked out on the base integration branch.
  - Base branch is dynamically resolved (checks `origin/HEAD` symref → `remote show origin` → known branch names: `unstable`, `develop`, `main`, `master`).
  - Blocks starting a ticket if the current branch is behind `origin/<base>` (performs a fast `git fetch` with a 2 s timeout before comparing).
  - Blocks starting a ticket if the current branch contains unmerged commits from another local feature/bugfix/techdebt branch.
- 24 new tests covering git safety enforcement (base-branch check, out-of-sync check, unmerged commits check, active-ticket limit); total 75 tests.

### Changed
- Bypassed the YouTrack testing lane, allowing finished tickets to move straight to `Done` or `Fixed` (removing `Test`/`Testing`/`Resolved` from allowed finished states).
- Updated `workflows-start-ticket.md`, `workflows-ai-codex-finish-ticket.md`, and `workflows-resolve-ticket.md` to instruct agents on starting the timer, filling Story points, stopping the timer, logging spent time, and bypassing the testing lane.
- Updated `workflows-git-origin-sync.md` and `rules-git-workflow.md` to reference the dynamically resolved base branch instead of the hardcoded `develop`.
- Auto-update block conditional in `hook_runtime.py` corrected to trigger when moving a ticket from `Ready` to `Active`.

### Fixed
- Workflow cycle execution gap: pre-tool hooks now actively verify YouTrack timer start/stop and spent time logging.

---

## [0.2.0] — 2026-06-07

### Added
- `sync_shared_assets(dest_root)` in `installer/cli.py`: copies `.agent/workflows/*.md` and `.agent/rules/*.md` to the destination project.
- `write_target_config(merged_config, config_path, dest_root)` in `installer/cli.py`: writes merged hook JSON at the correct relative config path.
- `--dest` flag on `scripts.installer.cli`: triggers real filesystem writes (hook config + shared asset sync) when provided.
- `YouTrackCheckResult` dataclass in `ticket_runtime.py`: structured return from transcript scanner with `reason` field (`ok` | `transcript_missing` | `state_not_found`).
- `CHANGELOG.md`.

### Changed
- Session-gate denial messages now use the dynamically resolved vault directory name — no project-specific strings remain in the runtime.
- `check_youtrack_state_in_transcript` returns `YouTrackCheckResult` instead of `bool`; denial messages now include the reason.
- `infer_is_bugfix_ticket` uses frontmatter-only inference — filename heuristic removed.
- README rewritten to reflect current architecture, correct installer CLI, test count, and release instructions.
- `plugin.json` author corrected from `"OpenAI"` to `"agentrick"`.
- `scripts/profiles/base.py` documented as v0.3 scaffolding.

### Fixed
- Portability: project-specific vault name no longer leaks into error messages delivered to other projects.
- Installer gap: `--dest` now delivers what the README promised.
- Bugfix false-positive: `debug-something.md` no longer routed to `Resolved/`.

> **Roadmap for v0.3**: wire `WorkspaceProfile` into `hook_runtime.py` and installer CLI; `--all-agents` target; configurable ticket folder names; GitLab tracker support.

---

## [0.1.1] — 2026-06-07

### Added
- Multi-host adapter hardening: `antigravity`, `claude`, `gemini`, and `codex` adapters now independently parse host-specific payload shapes and format decisions.
- `scripts/installer/` module with `cli.py`, `targets.py`, `merge.py`: non-destructive hook config merging per target host.
- `scripts/profiles/` scaffolding: `WorkspaceProfile` dataclass with `generic`, `flutter`, and `repository` presets (v0.2 wiring planned).
- `scripts/payload_capture.py`: debug payload capture utility gated by `CODEX_WORKFLOW_CAPTURE_DIR` env var.
- `scripts/release_packager.py`: versioned zip release builder.
- Contract test suite: 33 automated tests across adapters, policy engine, ticket runtime, profiles, and installer.

### Changed
- Refactored ticket lifecycle helpers into dedicated `scripts/ticket_runtime.py` module.
- `YouTrackCheckResult` dataclass replaces bare `bool` return from transcript scanner — callers now receive a structured reason (`ok` | `transcript_missing` | `state_not_found`).
- `infer_is_bugfix_ticket` uses frontmatter-only inference — filename heuristic removed to prevent false positives on files like `debug-something.md`.
- Session-gate denial messages now use the dynamically resolved vault directory name instead of the hard-coded `AI_Codex_SeuMeiSimples`.
- Installer `install()` gains `dest_root` parameter; when provided, writes hook config and syncs `.agent/workflows/` and `.agent/rules/` to the target project.
- Installer CLI gains `--dest` flag for real filesystem writes (existing `--output` flag retained for dry-run single-file output).
- `.codex-plugin/plugin.json` author corrected from `"OpenAI"` to `"agentrick"`.

### Fixed
- Portability bug: project-specific vault name no longer appears in error messages emitted to other projects.
- Installer promise gap: `--dest` now actually syncs workflows and writes the host config file as documented in the README.
- YouTrack denial messages now include diagnostic context (transcript missing vs. state not recorded).

---

## [0.1.0] — 2026-05-30

### Added
- Initial release of `codex-workflows-plugin`.
- `PreToolUse` hook enforcing session bootstrapping, destructive-deletion guard, markdown allowlist, and ticket lifecycle path validation (`Ready → Active → Closed/Resolved`).
- YouTrack state gating: blocks ticket moves/writes unless the corresponding card has been moved to the expected state in the conversation transcript.
- `hooks/hooks.json` for Codex host wiring.
- `.agent/workflows/` with 11 workflow markdown guides (start-ticket, resolve-ticket, atomic-commits, automated-tests, feature-implementation, git-origin-sync, jules-async, review-pr, tdd-bug-fix, ai-codex-finish-ticket, nano-banana).
- `.agent/rules/` with 27 coding and governance rule files.
- Plugin self-governance: the plugin's own `AI_Codex/` vault follows the conventions it enforces.
