"""
Tests for enforce-commit-skill.sh command matching.

Each command runs through the hook inside a temp git repo with no commit
state file, so exit 2 means "treated as a commit" and exit 0 means
"not a commit" (or the --amend exemption).

Run with: python3 -m unittest discover -s image/hooks/tests
"""

import json
import os
import subprocess
import tempfile
import unittest

HOOK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "enforce-commit-skill.sh",
)

COMMITS = [
    'git commit -m "x"',
    'git -C /repo commit -m "x"',
    "git --no-pager commit",
    "cd /repo && git commit -F msg.txt",
    'git add . && git commit -m "x"',
    "git -c core.editor=true commit",
    "GIT_AUTHOR_NAME=x git commit -m y",
    "/usr/bin/git commit -m y",
    'git -C "/path with space" commit -m y',
    "(cd /repo && git commit -m y)",
    "git --git-dir .git --work-tree . commit -m y",
    "git --git-dir=.git commit",
    "git commit;echo done",
    # A later --amend elsewhere must not exempt a plain commit
    "git commit -m y; git log --amend-check",
    "git commit -m a; git commit --amend --no-edit",
    'cd x && git commit -m "mention --amend"',
    # Mixed-quote, substitution and escaped-space arguments
    'git -c user.name="John Doe" commit -m x',
    "git -C $(pwd) commit -m x",
    "git -C ~/My\\ Repo commit -m x",
    "FOO=$(date) git commit -m x",
    # Brace groups and prefix commands
    "{ git commit -m x; }",
    "time git commit -m x",
    "exec git commit -m x",
    "sudo git commit -m x",
    "if true; then git commit -m x; fi",
    "echo $(git commit -m x)",
    # Prefix commands with their own options
    "sudo -u bob git commit -m x",
    "env -i git commit -m x",
    "timeout 60 git commit -m x",
    "nice -n 10 git commit -m x",
    # Nested substitution in a global option
    "git -C $(dirname $(pwd)) commit -m x",
    # A comment mentioning --amend doesn't exempt a plain commit
    "git commit -m x # --amend",
    # An apostrophe elsewhere can't hide a commit
    "echo don't && git commit -m x && echo it's",
]

NOT_COMMITS = [
    "git log --grep commit",
    "git log --oneline -- .husky/commit-msg",
    "git config --get commit.gpgsign",
    "git config commit.template ~/.gitmessage",
    "git show HEAD --stat commit",
    'git log -S "commit" --oneline',
    "git commit-tree HEAD^{tree} -m x",
    "git branch -D fix/commit-hook",
    "git checkout -b fix/commit-hook",
    'git log --format="%H commit %s"',
    "git rev-list --count HEAD # commit count",
    'echo "git commit"',
    'grep -rn "git commit" docs',
    "gh pr create --body-file - <<'EOF'\nSteps:\ngit log shows the commit\nEOF",
    # --amend is exempt
    "git commit --amend --no-edit",
    "git -C /repo commit --amend -m y",
    'git commit --amend -m "reword: it\'s fixed"',
    # Keywords inside quoted prose are not command boundaries
    'echo "now do git commit and push"',
    'gh pr create --body "Run sudo git commit -s to sign"',
]


class TestEnforceCommitSkillMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", cls.repo], check=True)

    def run_hook(self, command: str) -> int:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        return subprocess.run(
            ["bash", HOOK], input=payload, capture_output=True, text=True, cwd=self.repo
        ).returncode

    def test_commits_are_enforced(self):
        for command in COMMITS:
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(command), 2)

    def test_non_commits_pass(self):
        for command in NOT_COMMITS:
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(command), 0)


if __name__ == "__main__":
    unittest.main()
