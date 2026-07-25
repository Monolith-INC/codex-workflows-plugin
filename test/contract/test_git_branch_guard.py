import unittest
from unittest import mock

from scripts.policy.git_branch_guard import evaluate_git_branch_guard


class TestGitBranchGuard(unittest.TestCase):
    def test_denies_commit_on_master(self):
        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="master",
        ):
            decision = evaluate_git_branch_guard("git commit -m 'x'", "/tmp/repo")

        self.assertTrue(decision.is_denied())
        self.assertIn("protected branch `master`", decision.reason or "")

    def test_allows_commit_on_feature_branch(self):
        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="feature/ticket-123",
        ):
            decision = evaluate_git_branch_guard("git commit -m 'x'", "/tmp/repo")

        self.assertFalse(decision.is_denied())

    def test_allows_checkout_b_ticket_branch_from_trunk(self):
        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="main",
        ):
            decision = evaluate_git_branch_guard(
                "git checkout -b feature/session-guards",
                "/tmp/repo",
            )

        self.assertFalse(decision.is_denied())

    def test_denies_checkout_b_non_ticket_branch(self):
        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="develop",
        ):
            decision = evaluate_git_branch_guard("git checkout -b wip-stuff", "/tmp/repo")

        self.assertTrue(decision.is_denied())
        self.assertIn("feature/", decision.reason or "")

    def test_denies_checkout_protected_branch(self):
        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="feature/demo",
        ):
            decision = evaluate_git_branch_guard("git checkout unstable", "/tmp/repo")

        self.assertTrue(decision.is_denied())
        self.assertIn("protected branch `unstable`", decision.reason or "")

    def test_allows_path_restore_on_trunk(self):
        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="master",
        ):
            decision = evaluate_git_branch_guard("git checkout -- README.md", "/tmp/repo")

        self.assertFalse(decision.is_denied())

    def test_allows_status_on_trunk(self):
        with mock.patch(
            "scripts.policy.git_branch_guard._run_git_cmd",
            return_value="master",
        ):
            decision = evaluate_git_branch_guard("git status", "/tmp/repo")

        self.assertFalse(decision.is_denied())


if __name__ == "__main__":
    unittest.main()
