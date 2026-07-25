import os
from .events import CanonicalToolEvent, PolicyDecision

_VAULT_DELETE_TOOLS = frozenset({"Delete", "delete_file", "remove_file"})


def evaluate(event: CanonicalToolEvent) -> PolicyDecision:
    if _is_destructive_command(event):
        return PolicyDecision.deny(
            "Destructive deletions (rm) are forbidden on the AI Codex vault. Use 'mv' to change status."
        )

    if _is_vault_destructive_deletion(event):
        return PolicyDecision.deny(
            "Destructive deletions are forbidden on the AI Codex vault. Use 'mv' to change status."
        )

    if _is_markdown_denied(event):
        filename = (event.file_path or "").rsplit("/", 1)[-1]
        return PolicyDecision.deny(
            f"Read/write of {filename} blocked. Markdown files not in CLAUDE.md allowlist are forbidden."
        )

    ticket_decision = _evaluate_ticket_paths(event)
    if ticket_decision.is_denied():
        return ticket_decision

    if is_starting_ticket(event):
        start_decision = _validate_git_and_vault_on_start(event)
        if start_decision.is_denied():
            return start_decision

    if _requires_session(event) and not event.session_active and not _is_ticket_path(event) and "Agent_Sessions" not in (event.file_path or ""):
        vault_name = event.vault_dir.rsplit("/", 1)[-1] if event.vault_dir else "AI_Codex"
        return PolicyDecision.deny(
            f"Write blocked. You must initialize today's Agent Session log in {vault_name}/Agent_Sessions/ before making code modifications."
        )

    return PolicyDecision.allow()


def is_starting_ticket(event: CanonicalToolEvent) -> bool:
    """Detects if the tool event corresponds to starting/activating a ticket."""
    if event.source_path and event.destination_path:
        if "Tickets/Ready/" in event.source_path and "Tickets/Active/" in event.destination_path:
            return True
    if event.file_path and "Tickets/Active/" in event.file_path:
        if event.tool_name in ["write_to_file", "replace_file_content", "multi_replace_file_content", "Write", "StrReplace", "Edit"]:
            if not os.path.exists(event.file_path):
                return True
    return False


def _validate_git_and_vault_on_start(event: CanonicalToolEvent) -> PolicyDecision:
    """Enforces git safety and vault active-ticket limits when starting a ticket."""
    # 1. Check if another ticket is already active in vault
    if event.vault_dir:
        active_dir = None
        for root, dirs, files in os.walk(event.vault_dir):
            if root.endswith("Tickets/Active"):
                active_dir = root
                break
        if not active_dir:
            active_dir = os.path.join(event.vault_dir, "Tickets/Active")

        if os.path.exists(active_dir):
            active_files = [f for f in os.listdir(active_dir) if f.endswith(".md")]
            target_basename = ""
            if event.destination_path:
                target_basename = os.path.basename(event.destination_path)
            elif event.file_path:
                target_basename = os.path.basename(event.file_path)

            other_active = [f for f in active_files if f != target_basename]
            if other_active:
                return PolicyDecision.deny(
                    f"Cannot start a new ticket. There is already an active ticket in Tickets/Active: {', '.join(other_active)}. "
                    "Please resolve or close it first."
                )

    # Skip git checks if workspace_root is not configured or not a git repo
    if not event.workspace_root or not os.path.exists(os.path.join(event.workspace_root, ".git")):
        return PolicyDecision.allow()

    from .git_utils import (
        get_integration_branch,
        run_git_fetch,
        get_commits_behind_base,
        get_unmerged_commits_intersection,
        _run_git_cmd,
    )

    # 2. Get dynamic integration branch
    base_branch = get_integration_branch(event.workspace_root)

    # 3. Check if checked out on base branch
    current_branch = _run_git_cmd(["git", "branch", "--show-current"], event.workspace_root)
    if current_branch == base_branch:
        return PolicyDecision.deny(
            f"Cannot start a ticket while checked out on the base integration branch '{base_branch}'. "
            "Please check out a feature, bugfix, or techdebt branch first."
        )

    # 4. Fetch origin to get latest remote base status
    run_git_fetch(event.workspace_root, base_branch)

    # 5. Check if branch is out of sync/behind remote base
    behind_commits = get_commits_behind_base(event.workspace_root, base_branch)
    if behind_commits:
        return PolicyDecision.deny(
            f"Your current branch '{current_branch}' is out of sync (behind remote origin/{base_branch} by {len(behind_commits)} commits). "
            f"Please run git pull or merge/rebase with the latest remote origin/{base_branch} before starting work."
        )

    # 6. Check for unmerged commits from another feature/bugfix branch
    intersections = get_unmerged_commits_intersection(event.workspace_root, base_branch)
    if intersections:
        reasons = []
        for branch, commits in intersections.items():
            reasons.append(f"'{branch}' ({len(commits)} unmerged commits)")
        return PolicyDecision.deny(
            f"Your current branch contains unmerged commits from another feature/bugfix branch: {', '.join(reasons)}. "
            f"Please ensure those branches are merged into origin/{base_branch} and synced before starting a new ticket."
        )

    return PolicyDecision.allow()



def _is_destructive_command(event: CanonicalToolEvent) -> bool:
    command = (event.command or "").strip()
    if not command:
        return False
    vault_markers = {
        event.vault_dir,
        event.vault_dir.rsplit("/", 1)[-1] if event.vault_dir else "",
        "AI_Codex",
    }
    if any(marker and marker in command for marker in vault_markers):
        return "rm " in command or "rmdir " in command
    return False


def _is_vault_destructive_deletion(event: CanonicalToolEvent) -> bool:
    """Block native delete tools on vault paths (rm is already blocked for Shell)."""
    if event.tool_name not in _VAULT_DELETE_TOOLS:
        return False
    file_path = (event.file_path or "").strip()
    vault_dir = (event.vault_dir or "").strip()
    if not file_path or not vault_dir:
        return False
    try:
        abs_path = os.path.abspath(file_path)
        abs_vault = os.path.abspath(vault_dir)
    except (OSError, ValueError):
        return False
    return abs_path == abs_vault or abs_path.startswith(abs_vault + os.sep)


def _is_markdown_denied(event: CanonicalToolEvent) -> bool:
    return bool(event.file_path and event.file_path.endswith(".md") and not event.markdown_allowed)


def _requires_session(event: CanonicalToolEvent) -> bool:
    return event.tool_name in {
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
        "Write",
        "StrReplace",
        "Edit",
    }


def _evaluate_ticket_paths(event: CanonicalToolEvent) -> PolicyDecision:
    if event.file_path:
        if "Tickets/Resolved/" in event.file_path and not event.is_bugfix_ticket:
            return PolicyDecision.deny(
                "Only bugfix tickets can be written to Tickets/Resolved/. Feature/Task tickets must go to Tickets/Closed/."
            )
        if "Tickets/Closed/" in event.file_path and event.is_bugfix_ticket:
            return PolicyDecision.deny(
                "Bugfix tickets cannot be written to Tickets/Closed/. They must go to Tickets/Resolved/."
            )

    if event.source_path and event.destination_path:
        if "Tickets/Ready/" in event.source_path and "Tickets/Active/" not in event.destination_path:
            return PolicyDecision.deny(
                f"Tickets from Tickets/Ready/ must be moved to Tickets/Active/ when started, not {event.destination_path.rsplit('/', 1)[-1]}."
            )
        if "Tickets/Active/" in event.source_path:
            if event.is_bugfix_ticket and "Tickets/Resolved/" not in event.destination_path:
                return PolicyDecision.deny(
                    f"Bugfix ticket {event.source_path.rsplit('/', 1)[-1]} must be moved to Tickets/Resolved/, not {event.destination_path.rsplit('/', 1)[-1]}."
                )
            if not event.is_bugfix_ticket and "Tickets/Closed/" not in event.destination_path:
                return PolicyDecision.deny(
                    f"Feature/Task ticket {event.source_path.rsplit('/', 1)[-1]} must be moved to Tickets/Closed/, not {event.destination_path.rsplit('/', 1)[-1]}."
                )

    return PolicyDecision.allow()


def _is_ticket_path(event: CanonicalToolEvent) -> bool:
    return any(
        path and "Tickets/" in path
        for path in (event.file_path, event.source_path, event.destination_path)
    )
