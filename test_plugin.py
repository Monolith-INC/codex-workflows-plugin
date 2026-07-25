import os
import sys
import json
import tempfile
import shutil
import unittest
import subprocess
from datetime import datetime

# Resolve hook path relative to this test file
HOOK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills", "codex_workflows", "scripts", "codex_enforce_hook.py")

class TestCodexEnforceHook(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure representing a project
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create git root mock
        os.makedirs(os.path.join(self.test_dir, ".git"))
        self.vault_dir = os.path.join(self.test_dir, "AI_Codex_SeuMeiSimples")
        os.makedirs(self.vault_dir)
        
    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)
        
    def run_hook(self, stdin_data):
        process = subprocess.Popen(
            [sys.executable, HOOK_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=json.dumps(stdin_data))
        return json.loads(stdout.strip())
        
    def test_allow_generic_tool(self):
        stdin = {
            "name": "view_file",
            "arguments": {
                "AbsolutePath": os.path.join(self.test_dir, "lib", "main.dart")
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")
        
    def test_deny_destructive_delete(self):
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"rm -rf {self.vault_dir}"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("Destructive deletions", res["reason"])
        
    def test_deny_unallowed_markdown(self):
        unallowed_path = os.path.join(self.test_dir, "docs", "notes.md")
        stdin = {
            "name": "view_file",
            "arguments": {
                "AbsolutePath": unallowed_path
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("blocked", res["reason"])
        
    def test_allow_allowed_markdown(self):
        allowed_path = os.path.join(self.test_dir, "CLAUDE.md")
        stdin = {
            "name": "view_file",
            "arguments": {
                "AbsolutePath": allowed_path
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")
        
    def test_deny_write_without_session(self):
        code_file = os.path.join(self.test_dir, "lib", "utils.dart")
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": code_file
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("Write blocked. You must initialize today's Agent Session", res["reason"])
        
    def test_allow_write_with_session(self):
        # Create an active session file for today
        sessions_dir = os.path.join(self.vault_dir, "Agent_Sessions")
        os.makedirs(sessions_dir)
        today_str = datetime.now().strftime("%Y-%m-%d")
        session_file = os.path.join(sessions_dir, f"{today_str}-120000-session.md")
        with open(session_file, "w") as f:
            f.write("---\nnext: null\n---")
            
        code_file = os.path.join(self.test_dir, "lib", "utils.dart")
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": code_file
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_deny_shell_redirect_without_session(self):
        code_file = os.path.join(self.test_dir, "lib", "utils.dart")
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"echo 'code' > {code_file}"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("Write blocked. You must initialize today's Agent Session", res["reason"])

    def test_deny_shell_redirect_to_forbidden_markdown(self):
        sessions_dir = os.path.join(self.vault_dir, "Agent_Sessions")
        os.makedirs(sessions_dir)
        today_str = datetime.now().strftime("%Y-%m-%d")
        session_file = os.path.join(sessions_dir, f"{today_str}-120000-session.md")
        with open(session_file, "w") as f:
            f.write("---\nnext: null\n---")

        unallowed_path = os.path.join(self.test_dir, "docs", "notes.md")
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"echo secret > {unallowed_path}"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("blocked", res["reason"])

    def test_allow_shell_redirect_with_session(self):
        sessions_dir = os.path.join(self.vault_dir, "Agent_Sessions")
        os.makedirs(sessions_dir)
        today_str = datetime.now().strftime("%Y-%m-%d")
        session_file = os.path.join(sessions_dir, f"{today_str}-120000-session.md")
        with open(session_file, "w") as f:
            f.write("---\nnext: null\n---")

        code_file = os.path.join(self.test_dir, "lib", "utils.dart")
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"echo 'code' > {code_file}"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_allow_ticket_move_ready_to_active(self):
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Ready/task-123.md {self.vault_dir}/Tickets/Active/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_deny_ticket_move_ready_to_resolved(self):
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Ready/task-123.md {self.vault_dir}/Tickets/Resolved/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("must be moved to Tickets/Active/", res["reason"])

    def test_allow_bugfix_move_active_to_resolved(self):
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Active/bug-123.md {self.vault_dir}/Tickets/Resolved/bug-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_deny_bugfix_move_active_to_closed(self):
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Active/bug-123.md {self.vault_dir}/Tickets/Closed/bug-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("must be moved to Tickets/Resolved/", res["reason"])

    def test_allow_task_move_active_to_closed(self):
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Active/task-123.md {self.vault_dir}/Tickets/Closed/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_deny_task_move_active_to_resolved(self):
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Active/task-123.md {self.vault_dir}/Tickets/Resolved/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("must be moved to Tickets/Closed/", res["reason"])

    def test_deny_write_task_to_resolved(self):
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": f"{self.vault_dir}/Tickets/Resolved/task-123.md",
                "CodeContent": "---\ntype: task\n---"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("Only bugfix tickets can be written to Tickets/Resolved/", res["reason"])

    def test_deny_write_bugfix_to_closed(self):
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": f"{self.vault_dir}/Tickets/Closed/bug-123.md",
                "CodeContent": "---\ntype: bug\n---"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("Bugfix tickets cannot be written to Tickets/Closed/", res["reason"])

    def test_plugin_manifest_exists(self):
        manifest_path = os.path.join(self.old_cwd, ".codex-plugin", "plugin.json")
        self.assertTrue(os.path.isfile(manifest_path))

    def test_plugin_manifest_is_valid_codex_manifest(self):
        manifest_path = os.path.join(self.old_cwd, ".codex-plugin", "plugin.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["name"], "codex-workflows-plugin")
        self.assertIn("skills", manifest)
        self.assertIn("interface", manifest)
        self.assertNotIn("hooks", manifest)

    def create_mock_transcript(self, issue_id, state, timer=None, spent_time=None):
        transcript_file = os.path.join(self.test_dir, "mock_transcript.jsonl")
        custom_fields = {"State": state}
        if timer is not None:
            custom_fields["Timer"] = timer
        if spent_time is not None:
            custom_fields["Spent time"] = spent_time
        step = {
            "status": "DONE",
            "tool_calls": [
                {
                    "name": "call_mcp_tool",
                    "args": {
                        "ServerName": "youtrack",
                        "ToolName": "update_issue",
                        "Arguments": json.dumps({
                            "issueId": issue_id,
                            "customFields": custom_fields
                        })
                    }
                }
            ]
        }
        with open(transcript_file, "w") as f:
            f.write(json.dumps(step) + "\n")
        return transcript_file

    def test_deny_write_active_without_youtrack_update(self):
        # Create ticket content with YouTrack ID
        content = "---\nyoutrack: SEUMEI-501\ntype: task\nstatus: active\n---"
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": f"{self.vault_dir}/Tickets/Active/task-123.md",
                "CodeContent": content
            },
            "transcriptPath": os.path.join(self.test_dir, "nonexistent.jsonl")
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("You must update YouTrack issue", res["reason"])

    def test_allow_write_active_with_youtrack_update(self):
        # Create an active session file for today to pass session check
        sessions_dir = os.path.join(self.vault_dir, "Agent_Sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        session_file = os.path.join(sessions_dir, f"{today_str}-120000-session.md")
        with open(session_file, "w") as f:
            f.write("---\nnext: null\n---")

        transcript_path = self.create_mock_transcript("SEUMEI-501", "In Progress", timer="Start")
        content = "---\nyoutrack: SEUMEI-501\ntype: task\nstatus: active\n---"
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": f"{self.vault_dir}/Tickets/Active/task-123.md",
                "CodeContent": content
            },
            "transcriptPath": transcript_path
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_deny_write_closed_without_youtrack_done(self):
        content = "---\nyoutrack: SEUMEI-501\ntype: task\nstatus: closed\n---"
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": f"{self.vault_dir}/Tickets/Closed/task-123.md",
                "CodeContent": content
            },
            "transcriptPath": os.path.join(self.test_dir, "nonexistent.jsonl")
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("You must update YouTrack issue", res["reason"])

    def test_allow_write_closed_with_youtrack_done(self):
        sessions_dir = os.path.join(self.vault_dir, "Agent_Sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        session_file = os.path.join(sessions_dir, f"{today_str}-120000-session.md")
        with open(session_file, "w") as f:
            f.write("---\nnext: null\n---")

        transcript_path = self.create_mock_transcript("SEUMEI-501", "Done", timer="Stop", spent_time="2h")
        content = "---\nyoutrack: SEUMEI-501\ntype: task\nstatus: closed\n---"
        stdin = {
            "name": "write_to_file",
            "arguments": {
                "TargetFile": f"{self.vault_dir}/Tickets/Closed/task-123.md",
                "CodeContent": content
            },
            "transcriptPath": transcript_path
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "allow")

    def init_git_repo(self):
        # Helper to initialize a real git repo in test_dir
        git_dir = os.path.join(self.test_dir, ".git")
        if os.path.exists(git_dir):
            shutil.rmtree(git_dir)
        subprocess.run(["git", "init"], cwd=self.test_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        # Create a dummy commit to establish HEAD
        dummy_file = os.path.join(self.test_dir, "dummy.txt")
        with open(dummy_file, "w") as f:
            f.write("initial")
        subprocess.run(["git", "add", "dummy.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.test_dir, check=True)
        # Create develop branch
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=self.test_dir, check=True, capture_output=True)

    def test_deny_start_ticket_on_base_branch(self):
        self.init_git_repo()
        # Ensure we are checked out on 'develop'
        # Try to move a ticket from Ready to Active
        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Ready/task-123.md {self.vault_dir}/Tickets/Active/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("Cannot start a ticket while checked out on the base integration branch", res["reason"])

    def test_deny_start_ticket_out_of_sync(self):
        self.init_git_repo()
        # Checkout a feature branch from develop
        subprocess.run(["git", "checkout", "-b", "feature/my-task"], cwd=self.test_dir, check=True, capture_output=True)
        
        # Now make 'develop' ahead (simulate remote change by pointing origin/develop ahead)
        # In a real environment, we'd have a remote. Here, we can create refs/remotes/origin/develop pointing to a new commit.
        # Let's checkout develop, make a commit, then update remote ref, and checkout feature branch again
        subprocess.run(["git", "checkout", "develop"], cwd=self.test_dir, check=True, capture_output=True)
        dummy_file = os.path.join(self.test_dir, "dummy.txt")
        with open(dummy_file, "a") as f:
            f.write("\nmore content")
        subprocess.run(["git", "add", "dummy.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "develop commit"], cwd=self.test_dir, check=True)
        
        # Get the commit hash
        develop_hash = subprocess.check_output(["git", "rev-parse", "develop"], cwd=self.test_dir, text=True).strip()
        
        # Create origin/develop ref pointing to this new commit
        os.makedirs(os.path.join(self.test_dir, ".git", "refs", "remotes", "origin"), exist_ok=True)
        with open(os.path.join(self.test_dir, ".git", "refs", "remotes", "origin", "develop"), "w") as f:
            f.write(develop_hash + "\n")
            
        # Set origin/HEAD symref to point to origin/develop
        subprocess.run(["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop"], cwd=self.test_dir, check=True)

        # Checkout feature branch (which is now missing the new develop commit)
        subprocess.run(["git", "checkout", "feature/my-task"], cwd=self.test_dir, check=True, capture_output=True)

        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Ready/task-123.md {self.vault_dir}/Tickets/Active/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("out of sync", res["reason"])

    def test_deny_start_ticket_with_unmerged_commits(self):
        self.init_git_repo()
        
        # Set origin/develop tracking ref
        develop_hash = subprocess.check_output(["git", "rev-parse", "develop"], cwd=self.test_dir, text=True).strip()
        os.makedirs(os.path.join(self.test_dir, ".git", "refs", "remotes", "origin"), exist_ok=True)
        with open(os.path.join(self.test_dir, ".git", "refs", "remotes", "origin", "develop"), "w") as f:
            f.write(develop_hash + "\n")
        subprocess.run(["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop"], cwd=self.test_dir, check=True)

        # Create feature/other branch and make a commit
        subprocess.run(["git", "checkout", "-b", "feature/other"], cwd=self.test_dir, check=True, capture_output=True)
        with open(os.path.join(self.test_dir, "other.txt"), "w") as f:
            f.write("other changes")
        subprocess.run(["git", "add", "other.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "other commit"], cwd=self.test_dir, check=True)
        
        # Create feature/current branch off of feature/other (so it inherits the unmerged commit)
        subprocess.run(["git", "checkout", "-b", "feature/current"], cwd=self.test_dir, check=True, capture_output=True)

        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Ready/task-123.md {self.vault_dir}/Tickets/Active/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("contains unmerged commits from another feature/bugfix branch", res["reason"])

    def test_deny_start_ticket_when_another_active_exists(self):
        # Create active directory and an existing active ticket file
        active_dir = os.path.join(self.vault_dir, "Tickets", "Active")
        os.makedirs(active_dir, exist_ok=True)
        with open(os.path.join(active_dir, "task-999.md"), "w") as f:
            f.write("existing active ticket")

        stdin = {
            "name": "run_command",
            "arguments": {
                "CommandLine": f"mv {self.vault_dir}/Tickets/Ready/task-123.md {self.vault_dir}/Tickets/Active/task-123.md"
            }
        }
        res = self.run_hook(stdin)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("There is already an active ticket in Tickets/Active", res["reason"])

if __name__ == "__main__":
    unittest.main()
