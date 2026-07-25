"""Block mutating git on integration trunk branches."""

from __future__ import annotations

import re
import shlex

from .events import PolicyDecision
from .git_utils import _run_git_cmd

PROTECTED_BRANCHES = frozenset({"main", "master", "develop", "unstable"})
_TICKET_BRANCH_RE = re.compile(r"^(feature|bugfix|techdebt)/.+")

# Subcommands that change repo history/state and must not run on a trunk checkout.
_MUTATING_SUBCOMMANDS = frozenset(
    {
        "commit",
        "push",
        "merge",
        "rebase",
        "pull",
        "cherry-pick",
        "revert",
        "am",
        "reset",
        "stash",
        "tag",
        "notes",
        "svn",
    }
)

_CHECKOUT_SWITCH = frozenset({"checkout", "switch"})


def evaluate_git_branch_guard(command: str, workspace_root: str) -> PolicyDecision:
    """Deny mutating git / trunk checkouts while on a protected branch."""
    argv = _git_argv(command)
    if argv is None:
        return PolicyDecision.allow()

    current = (_run_git_cmd(["git", "branch", "--show-current"], workspace_root) or "").strip()
    sub = argv[0] if argv else ""

    if sub in _CHECKOUT_SWITCH:
        return _evaluate_checkout_switch(argv, current)

    if current not in PROTECTED_BRANCHES:
        return PolicyDecision.allow()

    if sub in _MUTATING_SUBCOMMANDS or sub.startswith("commit"):
        return PolicyDecision.deny(
            f"Git `{sub}` is blocked while checked out on protected branch `{current}`. "
            "Create and check out a ticket branch first "
            "(e.g. `git checkout -b feature/<ticket>-<slug>` or `bugfix/...` / `techdebt/...`)."
        )

    return PolicyDecision.allow()


def is_ticket_branch(name: str | None) -> bool:
    return bool(name and _TICKET_BRANCH_RE.match(name))


def _evaluate_checkout_switch(argv: list[str], current: str) -> PolicyDecision:
    creating = "-b" in argv or "-B" in argv or "-c" in argv or "-C" in argv or "--create" in argv
    target = _checkout_target(argv)

    if creating:
        # Creating/switching to a new branch from trunk is the required escape hatch.
        if target and target in PROTECTED_BRANCHES:
            return PolicyDecision.deny(
                f"Refusing to create protected branch `{target}`. "
                "Use a ticket branch name under feature/, bugfix/, or techdebt/."
            )
        if target and not is_ticket_branch(target):
            return PolicyDecision.deny(
                f"Refusing to create `{target}`. Ticket branches must start with "
                "`feature/`, `bugfix/`, or `techdebt/`."
            )
        return PolicyDecision.allow()

    if target and target in PROTECTED_BRANCHES:
        return PolicyDecision.deny(
            f"Refusing to check out protected branch `{target}`. "
            "Stay on (or create) a ticket branch for implementation work."
        )

    if current in PROTECTED_BRANCHES and not target:
        # e.g. git checkout -- file  (path restore) — allow
        if "--" in argv:
            return PolicyDecision.allow()

    return PolicyDecision.allow()


def _git_argv(command: str) -> list[str] | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if not tokens:
        return None

    # Handle `git -C path ...` and env prefixes lightly: find first bare `git`.
    try:
        idx = next(i for i, tok in enumerate(tokens) if tok == "git" or tok.endswith("/git"))
    except StopIteration:
        return None

    rest = tokens[idx + 1 :]
    # skip global git options before subcommand
    while rest and rest[0].startswith("-"):
        opt = rest.pop(0)
        if opt in {"-C", "-c"} and rest:
            rest.pop(0)
    return rest


def _checkout_target(argv: list[str]) -> str | None:
    """Best-effort target ref for checkout/switch."""
    args = argv[1:]
    for flag in ("-b", "-B", "-c", "-C"):
        if flag in args:
            i = args.index(flag)
            if i + 1 < len(args) and not args[i + 1].startswith("-"):
                return args[i + 1]

    skip_next = False
    positionals: list[str] = []
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            break
        if token in {"-b", "-B", "-c", "-C", "--branch", "--conflict", "--orphan"}:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        positionals.append(token)
    return positionals[0] if positionals else None
