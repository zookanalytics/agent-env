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
]


class TestPreventBashSensitiveArgs(unittest.TestCase):
    def test_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command), 0)

    def test_blocked(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertEqual(run_hook(command), 2)


if __name__ == "__main__":
    unittest.main()
