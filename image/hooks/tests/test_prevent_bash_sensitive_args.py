"""
Tests for prevent-bash-sensitive-args.py.

Run with: python3 -m unittest discover -s image/hooks/tests
"""

import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prevent-bash-sensitive-args.py",
)


def run_hook(command: str) -> int:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, HOOK], input=payload, capture_output=True, text=True
    )
    return result.returncode


ALLOWED = [
    # Heredoc bodies with apostrophes (shlex reports "No closing quotation")
    "gh pr create --title \"feat: x\" --body-file - <<'EOF'\n"
    "## Summary\nIt's the ESP32's own reading, don't worry\nEOF",
    "git commit -F - <<EOF\nfix: the hook's parser\nEOF",
    # Comment with an apostrophe
    "git status  # don't",
    "ls -la",
    "cp .env.example .env.sample",
    "export API_KEY=abc123",
    "git commit -m \"fix: handle the user's input\"",
    "python3 -c \"import json; print(json.dumps({'a': 1}))\"",
    "cd /tmp && npm test 2>&1 | tail -20",
    # Quoted prose must stay one token (no *_key / *-key false positives)
    'git commit -m "fix primary_key lookup in users"',
    'gh pr create --title "Rotate ssh-key handling"',
    "psql -c \"SELECT * FROM t WHERE api_key = 1\"",
    # `#` inside quotes is not a comment; `<<` inside quotes is not a heredoc
    "echo \"# don't\" && echo '<<EOF'",
    # <<- heredoc with tab-indented delimiter, then more commands
    "cat <<-EOF\n\tit's fine\n\tEOF\necho done",
    # Two heredocs on one line
    "paste <(cat <<A\nit's a\nA\n) <(cat <<B\nit's b\nB\n)",
]

BLOCKED = [
    "cat .env",
    "cat .e''nv",
    "cat $(echo id_rsa)",
    "cat <<EOF > .env\nit's\nEOF",
    "bash <<'EOF'\ncat ~/.aws/credentials # it's fine\nEOF",
    "echo \"x\" > secrets.txt; echo 'unclosed",
    # Appending an unbalanced quote must not downgrade the check
    "cat .e''nv # '",
    # Operator glued to a safe suffix
    "cat .env;#.env.example",
    # Line continuation splitting the name
    "cat .e\\\nnv",
    "cat .e\\\nnv # '",
    # ANSI-C quoting splitting the name
    "cat .e$'n'v",
    "cat .e$'n'v # '",
    # Glued to operators
    "cat .env|wc -l",
    "cat $(echo .env)",
    # Heredoc body that is a script
    "bash <<EOF\ncat .e''nv\nEOF",
    # Real syntax errors are still blocked (bash would fail too)
    "echo 'unclosed",
]


def run_hook_raw(payload: str) -> int:
    return subprocess.run(
        [sys.executable, HOOK], input=payload, capture_output=True, text=True
    ).returncode


class TestPreventBashSensitiveArgs(unittest.TestCase):
    def test_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command), 0)

    def test_blocked(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command), 2)

    def test_bad_input_fails_closed(self):
        self.assertEqual(run_hook_raw("not json"), 2)
        self.assertEqual(
            run_hook_raw(json.dumps({"tool_name": "Bash", "tool_input": "cat x"})), 2
        )

    def test_non_bash_tool_ignored(self):
        self.assertEqual(run_hook_raw(json.dumps({"tool_name": "Read", "tool_input": {}})), 0)


if __name__ == "__main__":
    unittest.main()
