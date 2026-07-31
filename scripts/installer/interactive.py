"""Interactive, step-by-step installer wizard for codex-workflows-plugin."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

_PROJECT_MARKERS = (
    ".git",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "Gemfile",
    ".codex-plugin",
    "AI_Codex",
)

_TARGET_CHOICES = (
    ("all-agents", "All supported agent hosts (recommended)"),
    ("claude", "Claude Code / Claude CLI"),
    ("codex", "Codex CLI / IDE"),
    ("cursor", "Cursor IDE"),
    ("gemini", "Gemini CLI (deprecated)"),
    ("antigravity", "Antigravity IDE"),
)


@dataclass
class WizardAnswers:
    dest: Path
    target: str = "all-agents"
    uninstall: bool = False
    keep_runtime: bool = False


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    remediable: bool = False
    remedy_key: str | None = None


@dataclass
class WizardIO:
    stdin: TextIO
    stdout: TextIO
    ask: Callable[..., str] | None = None
    close_stdin: bool = False


def detect_software_project(path: Path) -> tuple[bool, list[str]]:
    """Return whether path looks like a software project and which markers matched."""
    matches: list[str] = []
    for marker in _PROJECT_MARKERS:
        candidate = path / marker
        if candidate.exists():
            matches.append(marker)
    return bool(matches), matches


def open_console_io() -> WizardIO | None:
    """Attach to an interactive console for prompts.

    Prefer ``/dev/tty`` so ``curl | bash`` can still prompt (stdin is the pipe).
    Fall back to ``sys.stdin``/``sys.stdout`` when those are attached to a TTY
    (IDE terminals or environments where ``/dev/tty`` is unavailable).
    """
    try:
        tty = open("/dev/tty", "r+", encoding="utf-8", errors="replace")  # noqa: SIM115
    except OSError:
        tty = None
    if tty is not None:
        return WizardIO(stdin=tty, stdout=tty, close_stdin=True)

    stdin = sys.stdin
    stdout = sys.stdout
    if stdin is None or stdout is None:
        return None
    try:
        if stdin.isatty() and stdout.isatty():
            return WizardIO(stdin=stdin, stdout=stdout, close_stdin=False)
    except ValueError:
        return None
    return None


def _print(io: WizardIO, message: str = "") -> None:
    io.stdout.write(message + "\n")
    io.stdout.flush()


def _ask(io: WizardIO, prompt: str, *, default: str | None = None) -> str:
    if io.ask is not None:
        return io.ask(prompt, default=default)
    suffix = f" [{default}]" if default not in (None, "") else ""
    io.stdout.write(f"{prompt}{suffix}: ")
    io.stdout.flush()
    raw = io.stdin.readline()
    if raw == "":
        raise EOFError("No input available on the terminal")
    value = raw.strip()
    if not value and default is not None:
        return default
    return value


def _ask_yes_no(io: WizardIO, prompt: str, *, default: bool = True) -> bool:
    default_token = "Y/n" if default else "y/N"
    while True:
        answer = _ask(io, f"{prompt} ({default_token})", default="y" if default else "n").lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        if answer == "" and default is not None:
            return default
        _print(io, "Please answer yes or no.")


def _ask_choice(io: WizardIO, prompt: str, choices: list[tuple[str, str]], *, default: str) -> str:
    _print(io, prompt)
    for index, (value, label) in enumerate(choices, start=1):
        marker = " (default)" if value == default else ""
        _print(io, f"  {index}. {value} — {label}{marker}")
    while True:
        answer = _ask(io, "Choose a number or id", default=default)
        if answer.isdigit():
            idx = int(answer)
            if 1 <= idx <= len(choices):
                return choices[idx - 1][0]
        for value, _label in choices:
            if answer == value:
                return value
        _print(io, "Invalid choice. Enter a listed number or id.")


def collect_answers(io: WizardIO, *, cwd: Path | None = None) -> WizardAnswers:
    cwd = (cwd or Path.cwd()).resolve()
    _print(io, "")
    _print(io, "=" * 70)
    _print(io, "  codex-workflows-plugin — interactive installer")
    _print(io, "=" * 70)
    _print(
        io,
        textwrap.dedent(
            """
            This wizard installs the plugin into one project (never into $HOME).
            You can cancel with Ctrl-C at any prompt.
            """
        ).strip(),
    )

    mode = _ask_choice(
        io,
        "What do you want to do?",
        [
            ("install", "Install / re-wire the plugin into a project"),
            ("uninstall", "Uninstall managed plugin assets from a project"),
        ],
        default="install",
    )

    is_project, markers = detect_software_project(cwd)
    dest: Path | None = None
    if is_project:
        _print(io, "")
        _print(io, f"Detected a software project in the current directory:\n  {cwd}")
        _print(io, "Markers: " + ", ".join(markers))
        if _ask_yes_no(io, "Use this folder as the install destination?", default=True):
            dest = cwd

    while dest is None:
        raw = _ask(io, "Project destination path", default=str(cwd))
        candidate = Path(raw).expanduser().resolve()
        if not candidate.exists():
            if _ask_yes_no(io, f"{candidate} does not exist. Create it?", default=True):
                candidate.mkdir(parents=True, exist_ok=True)
            else:
                continue
        if not candidate.is_dir():
            _print(io, "Destination must be a directory.")
            continue
        looks_like, found = detect_software_project(candidate)
        if not looks_like:
            _print(io, f"No common project markers found under {candidate}.")
            if not _ask_yes_no(io, "Continue with this destination anyway?", default=False):
                continue
        else:
            _print(io, "Project markers: " + ", ".join(found))
        dest = candidate

    if mode == "uninstall":
        keep_runtime = _ask_yes_no(io, "Keep the runtime directory (.codex-workflows)?", default=False)
        _print(io, "")
        _print(io, "Summary")
        _print(io, f"  Action : uninstall")
        _print(io, f"  Dest   : {dest}")
        _print(io, f"  Keep runtime: {'yes' if keep_runtime else 'no'}")
        if not _ask_yes_no(io, "Proceed?", default=True):
            raise SystemExit("Cancelled.")
        return WizardAnswers(dest=dest, uninstall=True, keep_runtime=keep_runtime)

    target = _ask_choice(
        io,
        "Which agent host(s) should receive hooks?",
        list(_TARGET_CHOICES),
        default="all-agents",
    )

    _print(io, "")
    _print(io, "Summary")
    _print(io, f"  Action : install")
    _print(io, f"  Dest   : {dest}")
    _print(io, f"  Target : {target}")
    if not _ask_yes_no(io, "Proceed with installation?", default=True):
        raise SystemExit("Cancelled.")
    return WizardAnswers(dest=dest, target=target)


def run_bootstrap(
    answers: WizardAnswers,
    *,
    zip_path: Path | None,
    install_dir: Path | None = None,
) -> int:
    from scripts.installer import bootstrap as bootstrap_mod

    argv = []
    if zip_path is not None:
        argv.append(str(zip_path))
    argv.extend(["--dest", str(answers.dest)])
    if answers.uninstall:
        argv.append("--uninstall")
        if answers.keep_runtime:
            argv.append("--keep-runtime")
    else:
        argv.extend(["--target", answers.target])
    if install_dir is not None:
        argv.extend(["--install-dir", str(install_dir)])

    old_argv = sys.argv
    try:
        sys.argv = ["bootstrap.py", *argv]
        return int(bootstrap_mod.main())
    finally:
        sys.argv = old_argv


def verify_install(dest: Path, target: str) -> list[CheckResult]:
    """Validate common post-install path / environment mismatches."""
    dest = dest.resolve()
    runtime = dest / ".codex-workflows"
    checks: list[CheckResult] = []

    def add(name: str, ok: bool, detail: str, *, remediable: bool = False, remedy_key: str | None = None) -> None:
        checks.append(CheckResult(name, ok, detail, remediable=remediable, remedy_key=remedy_key))

    add(
        "python3",
        shutil.which("python3") is not None,
        "python3 is on PATH" if shutil.which("python3") else "python3 not found on PATH",
    )

    version = sys.version_info
    add(
        "python-version",
        version >= (3, 10),
        f"Python {version.major}.{version.minor}.{version.micro} (3.10+ required)",
        remediable=False,
    )

    add(
        "dest-dir",
        dest.is_dir(),
        f"{dest} exists" if dest.is_dir() else f"{dest} is missing",
        remediable=False,
    )

    git_ok = (dest / ".git").exists() or _run_ok(["git", "-C", str(dest), "rev-parse", "--is-inside-work-tree"])
    add(
        "git-repo",
        git_ok,
        "destination is a git work tree" if git_ok else "destination is not a git repository (ticket-start git checks need git)",
    )

    add(
        "runtime-dir",
        runtime.is_dir(),
        f"{runtime} exists" if runtime.is_dir() else f"runtime missing at {runtime}",
        remediable=True,
        remedy_key="rewire",
    )

    hook_script = runtime / "skills" / "codex_workflows" / "scripts" / "claude_enforce_hook.py"
    add(
        "runtime-hooks",
        hook_script.is_file(),
        "hook entrypoints present" if hook_script.is_file() else f"missing {hook_script}",
        remediable=True,
        remedy_key="rewire",
    )

    expected_configs = {
        "all-agents": [".claude/settings.json", ".cursor/hooks.json", "hooks/hooks.json"],
        "claude": [".claude/settings.json"],
        "cursor": [".cursor/hooks.json"],
        "codex": ["hooks/hooks.json"],
        "gemini": [".gemini/settings.json"],
        "antigravity": [".agents/hooks.json"],
    }
    for rel in expected_configs.get(target, expected_configs["all-agents"]):
        path = dest / rel
        add(
            f"hook-config:{rel}",
            path.is_file(),
            f"{rel} present" if path.is_file() else f"{rel} missing",
            remediable=True,
            remedy_key="rewire",
        )

    mcp_path = dest / ".mcp.json"
    orchestrator_ok = False
    pythonpath_ok = False
    skills_ok = False
    if mcp_path.is_file():
        try:
            payload = json.loads(mcp_path.read_text(encoding="utf-8"))
            server = (payload.get("mcpServers") or {}).get("agentic-orchestrator") or {}
            env = server.get("env") or {}
            orchestrator_ok = isinstance(server, dict) and bool(server.get("command"))
            pythonpath = Path(str(env.get("PYTHONPATH", "")))
            skills_dir = Path(str(env.get("ORCHESTRATOR_SKILLS_DIR", "")))
            pythonpath_ok = pythonpath.is_dir()
            skills_ok = skills_dir.is_dir()
        except json.JSONDecodeError:
            orchestrator_ok = False
    add(
        "mcp-orchestrator",
        orchestrator_ok,
        "agentic-orchestrator present in .mcp.json" if orchestrator_ok else ".mcp.json missing agentic-orchestrator",
        remediable=True,
        remedy_key="rewire",
    )
    add(
        "mcp-pythonpath",
        pythonpath_ok,
        "ORCHESTRATOR PYTHONPATH exists" if pythonpath_ok else "ORCHESTRATOR PYTHONPATH missing or invalid",
        remediable=True,
        remedy_key="rewire",
    )
    add(
        "mcp-skills-dir",
        skills_ok,
        "ORCHESTRATOR_SKILLS_DIR exists" if skills_ok else "ORCHESTRATOR_SKILLS_DIR missing or invalid",
        remediable=True,
        remedy_key="rewire",
    )

    import_ok = False
    import_detail = "skipped (runtime PYTHONPATH unavailable)"
    if pythonpath_ok:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import scripts.orchestrator.mcp_server as m; print(m.__name__)",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(runtime.resolve())},
        )
        import_ok = proc.returncode == 0
        import_detail = (
            "scripts.orchestrator.mcp_server import ok"
            if import_ok
            else f"import failed: {(proc.stderr or proc.stdout).strip()}"
        )
    add(
        "orchestrator-import",
        import_ok,
        import_detail,
        remediable=True,
        remedy_key="rewire",
    )

    cursor_mcp = dest / ".cursor" / "mcp.json"
    add(
        "cursor-mcp",
        cursor_mcp.is_file(),
        ".cursor/mcp.json present" if cursor_mcp.is_file() else ".cursor/mcp.json missing",
        remediable=True,
        remedy_key="rewire",
    )

    claude_local = dest / ".claude" / "settings.local.json"
    claude_ok = False
    if claude_local.is_file():
        try:
            payload = json.loads(claude_local.read_text(encoding="utf-8"))
            enabled = payload.get("enabledMcpjsonServers") or []
            claude_ok = payload.get("enableAllProjectMcpServers") is True and "agentic-orchestrator" in enabled
        except json.JSONDecodeError:
            claude_ok = False
    add(
        "claude-mcp-enablement",
        claude_ok,
        "Claude local MCP enablement present"
        if claude_ok
        else ".claude/settings.local.json missing orchestrator enablement",
        remediable=True,
        remedy_key="rewire",
    )

    return checks


def _run_ok(command: list[str]) -> bool:
    try:
        return subprocess.run(command, capture_output=True, text=True).returncode == 0
    except OSError:
        return False


def report_checks(io: WizardIO, checks: list[CheckResult]) -> list[CheckResult]:
    _print(io, "")
    _print(io, "=" * 70)
    _print(io, "  Post-install verification")
    _print(io, "=" * 70)
    failed = [check for check in checks if not check.ok]
    for check in checks:
        mark = "OK " if check.ok else "FAIL"
        _print(io, f"  [{mark}] {check.name}: {check.detail}")
    _print(io, "")
    if not failed:
        _print(io, "All checks passed.")
        _print(io, "Restart your agent session in this project so hooks and MCP reload.")
    else:
        _print(io, f"{len(failed)} check(s) failed.")
        remediable = [check for check in failed if check.remediable]
        if remediable:
            _print(io, "Some failures can be retried by re-running the installer wiring step.")
        else:
            _print(io, "Remaining failures look like environment mismatches to fix manually.")
    return failed


def remediation_loop(
    io: WizardIO,
    answers: WizardAnswers,
    *,
    zip_path: Path | None,
    install_dir: Path | None = None,
) -> int:
    attempts = 0
    while True:
        attempts += 1
        checks = verify_install(answers.dest, answers.target)
        failed = report_checks(io, checks)
        if not failed:
            return 0

        remediable = [check for check in failed if check.remediable and check.remedy_key == "rewire"]
        if remediable and _ask_yes_no(
            io,
            "Re-run install wiring for the failed checks?",
            default=True,
        ):
            code = run_bootstrap(answers, zip_path=zip_path, install_dir=install_dir)
            if code != 0:
                _print(io, f"Re-wire exited with status {code}.")
            continue

        if attempts < 3 and _ask_yes_no(
            io,
            "Re-run verification only (after fixing things yourself)?",
            default=False,
        ):
            continue

        _print(io, "Leaving installer. Fix the failed checks, then re-run install.sh if needed.")
        return 1


def _no_tty_error(cwd: Path | None) -> int:
    dest = (cwd or Path.cwd()).resolve()
    print(
        "error: no interactive terminal available.\n"
        "Open a real terminal (or use an IDE terminal that allocates a TTY), or pass --dest:\n"
        f"  curl -fsSL .../install.sh | bash -s -- --dest {dest}",
        file=sys.stderr,
    )
    looks_like, markers = detect_software_project(dest)
    if looks_like:
        print(
            f"note: {dest} looks like a software project ({', '.join(markers)}).",
            file=sys.stderr,
        )
    return 2


def run_wizard(
    *,
    zip_path: Path | None = None,
    install_dir: Path | None = None,
    cwd: Path | None = None,
    io: WizardIO | None = None,
) -> int:
    close_stdin = False
    if io is None:
        io = open_console_io()
        if io is None:
            return _no_tty_error(cwd)
        close_stdin = io.close_stdin
    try:
        answers = collect_answers(io, cwd=cwd)
        code = run_bootstrap(answers, zip_path=zip_path, install_dir=install_dir)
        if answers.uninstall:
            return code
        if code != 0:
            _print(io, f"Install exited with status {code}.")
            if _ask_yes_no(io, "Run verification anyway?", default=True):
                return remediation_loop(io, answers, zip_path=zip_path, install_dir=install_dir)
            return code
        return remediation_loop(io, answers, zip_path=zip_path, install_dir=install_dir)
    except KeyboardInterrupt:
        _print(io, "\nCancelled.")
        return 130
    finally:
        if close_stdin and io is not None:
            io.stdin.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactive installer for codex-workflows-plugin")
    parser.add_argument("--zip", type=Path, default=None, help="Release zip path")
    parser.add_argument("--install-dir", type=Path, default=None, help="Optional runtime install dir")
    parser.add_argument("--cwd", type=Path, default=None, help="Override detection cwd (tests)")
    args = parser.parse_args(argv)
    return run_wizard(zip_path=args.zip, install_dir=args.install_dir, cwd=args.cwd)


if __name__ == "__main__":
    raise SystemExit(main())
