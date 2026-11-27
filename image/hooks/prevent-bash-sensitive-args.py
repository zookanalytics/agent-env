#!/usr/bin/env python3
"""
prevent-bash-sensitive-args.py

PreToolUse hook for Bash commands that prevents any bash command from
referencing sensitive filenames as arguments.

This prevents bypassing file access controls via indirect operations like:
- mv credentials.json safe.json (rename to bypass read protection)
- cp .env .env.backup (copy sensitive files)
- cat id_rsa (read via bash instead of Read tool)
- rm secrets.txt (delete sensitive files)

The hook first removes what shlex cannot parse but bash can: heredoc
bodies and # comments (via a small quote-aware scanner, which also joins
line continuations and unwraps $'..' / $".." quoting). The remainder is
tokenized with shlex, splitting on shell operators so `.env;#x` style gluing
can't hide a name. Heredoc bodies may be scripts, so they are scanned word by
word. Each token is checked against sensitive filename patterns, and command
substitutions $(...) and backticks are checked recursively. A command that
still can't be parsed is malformed and is blocked.

Exit codes:
    0 - Command is allowed
    2 - Command is blocked (provides feedback to Claude)
"""

import json
import os
import re
import shlex
import sys

# Add lib directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(SCRIPT_DIR, 'lib')
sys.path.insert(0, LIB_DIR)

from patterns import is_sensitive_file


def extract_command_substitutions(token: str) -> list[str]:
    """
    Extract inner commands from $(...) and backtick substitutions.

    Handles both styles of command substitution:
    - Modern: $(command)
    - Legacy: `command`

    Args:
        token: A shell token that may contain command substitutions

    Returns:
        List of inner command strings extracted from substitution constructs
    """
    results = []
    i = 0
    while i < len(token):
        if token[i:i+2] == '$(':
            # Handle $(...) - find matching ) by counting depth
            depth = 1
            start = i + 2
            j = start
            while j < len(token) and depth > 0:
                if token[j:j+2] == '$(':
                    depth += 1
                    j += 1
                elif token[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0:
                # Extract the inner command (excluding the closing paren)
                results.append(token[start:j-1])
            i = j
        elif token[i] == '`':
            # Handle backtick substitution - find matching backtick
            start = i + 1
            j = start
            while j < len(token) and token[j] != '`':
                j += 1
            if j < len(token):
                # Found closing backtick
                results.append(token[start:j])
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return results


_HEREDOC_START = re.compile(r"<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([^\s;|&<>()]+))")
_WORD_SPLIT = re.compile(r"[\s;|&<>()`$]+")
_COMMENT_PRECEDERS = set(" \t\n;|&()")


def strip_heredocs_and_comments(command: str) -> tuple[str, list[str]]:
    """
    Split a command into (shell text, heredoc bodies).

    Walks the command tracking quote state so that `#` and `<<` inside
    quotes are left alone. Outside quotes it:
      - drops `# ...` comments up to the end of the line
      - drops backslash-newline line continuations
      - unwraps $'..' and $".." by dropping the `$` (shlex then sees a
        plain quoted string, so `.e$'n'v` tokenizes as `.env`)
      - removes heredoc bodies from the shell text and returns them
        separately (the `<<DELIM` operator itself stays in the text)

    Unbalanced quotes are left in place; shlex reports them later.
    """
    out = []
    bodies = []
    pending = []  # (delimiter, strip_tabs) awaiting their bodies
    i, n = 0, len(command)
    quote = None
    while i < n:
        c = command[i]
        if quote == "'":
            out.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n:
                out.append(command[i:i + 2])
                i += 2
                continue
            out.append(c)
            if c == '"':
                quote = None
            i += 1
            continue
        # Outside quotes
        if c == "\\" and i + 1 < n:
            if command[i + 1] != "\n":  # line continuation: drop both
                out.append(command[i:i + 2])
            i += 2
            continue
        if c in "'\"":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "$" and i + 1 < n and command[i + 1] in "'\"":
            i += 1  # drop `$` of $'..' / $".."
            continue
        if c == "#" and (i == 0 or command[i - 1] in _COMMENT_PRECEDERS):
            while i < n and command[i] != "\n":
                i += 1
            continue
        if command.startswith("<<", i) and not command.startswith("<<<", i):
            m = _HEREDOC_START.match(command, i)
            if m:
                delim = next(g for g in m.groups()[1:] if g is not None)
                pending.append((delim, m.group(1) == "-"))
                out.append(m.group(0))
                i = m.end()
                continue
        if c == "\n" and pending:
            out.append(c)
            i += 1
            for delim, strip_tabs in pending:
                body = []
                while i < n:
                    end = command.find("\n", i)
                    end = n if end == -1 else end
                    line = command[i:end]
                    i = end + 1
                    if (line.lstrip("\t") if strip_tabs else line) == delim:
                        break
                    body.append(line)
                bodies.append("\n".join(body))
            pending = []
            continue
        out.append(c)
        i += 1
    return "".join(out), bodies


def shell_tokens(text: str) -> list[str]:
    """
    Tokenize shell text with shlex, splitting on operators (; | & < > ( ))
    so a token glued to an operator can't hide or rename a filename.

    Raises:
        ValueError: If the text is malformed (unbalanced quotes)
    """
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""  # comments were already stripped
    return list(lexer)


def body_tokens(body: str) -> list[str]:
    """
    Word-split a heredoc body (it may be a script fed to a shell).
    A second pass with quotes removed catches `.e''nv` style gluing.
    """
    tokens = []
    for variant in (body, re.sub(r"[\"'\\]", "", body)):
        tokens.extend(t.strip("\"'\\") for t in _WORD_SPLIT.split(variant))
    return [t for t in tokens if t]


def parse_command_tokens(command: str) -> list[str]:
    """
    Tokens to check: shell-parsed tokens of the command (heredoc bodies and
    comments removed) plus word-split tokens of each heredoc body.

    Raises:
        ValueError: If the command (minus heredocs/comments) is malformed
    """
    text, bodies = strip_heredocs_and_comments(command)
    tokens = shell_tokens(text)
    for body in bodies:
        tokens.extend(body_tokens(body))
    return tokens


def contains_sensitive_filename(command: str, _depth: int = 0) -> tuple[bool, str]:
    """
    Check if command contains any sensitive filename pattern.

    Tokenizes via parse_command_tokens (shlex on the command minus heredoc
    bodies and comments, plus word-split heredoc bodies). Each token is
    checked against sensitive file patterns, with safe patterns (like
    .env.example) allowed through.

    Raises:
        ValueError: If command syntax is malformed

    Command substitutions $(...) and backticks are recursively parsed
    and checked.

    Args:
        command: The shell command to check
        _depth: Internal recursion depth counter (max 10)

    Returns:
        Tuple of (is_sensitive, matched_token)
        - is_sensitive: True if command contains sensitive filename
        - matched_token: The token/reason that matched (empty if none)
    """
    # Prevent infinite recursion - fail closed for security
    if _depth > 10:
        return True, "recursion depth exceeded"

    for token in parse_command_tokens(command):
        # Check for command substitutions - recursively check inner content
        inner_commands = extract_command_substitutions(token)
        if inner_commands:
            for inner_cmd in inner_commands:
                is_sensitive, match = contains_sensitive_filename(inner_cmd, _depth + 1)
                if is_sensitive:
                    return True, f"{match} (in substitution)"

        # Always check the token itself (even if it contains substitutions)
        # This catches cases like "$(echo foo).env" where .env is in outer token
        if is_sensitive_file(token):
            return True, token

    return False, ""


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        # Fail closed: exit 1 is non-blocking in Claude Code
        print(f"🚫 Bash command blocked: invalid hook input: {e}", file=sys.stderr)
        sys.exit(2)

    # Fail closed on any unexpected error: an uncaught exception exits 1,
    # which Claude Code treats as non-blocking and would let the command run.
    try:
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input') or {}

        # Only process Bash commands
        if tool_name != 'Bash':
            sys.exit(0)

        command = tool_input.get('command', '')
        if not command:
            sys.exit(0)

        is_sensitive, matched_pattern = contains_sensitive_filename(command)
    except ValueError as e:
        print(f"""🚫 Bash command blocked: malformed command syntax.

Could not parse command (unclosed quotes, invalid escapes, etc.).
Heredoc bodies and # comments are ignored, so this is a real syntax error.

Parse error: {e}
Command: {command}

Fix the command syntax and try again.
""", file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # noqa: BLE001
        print(f"🚫 Bash command blocked: sensitive-args hook error: {e}",
              file=sys.stderr)
        sys.exit(2)

    if is_sensitive:
        print(f"""🚫 Bash command blocked: contains sensitive filename pattern.

The command references a file that matches sensitive file patterns.
This is blocked to prevent bypassing file access controls.

Matched pattern: {matched_pattern}

Command: {command}

Why this is blocked:
Bash commands can bypass Read/Edit/Write hooks by directly accessing files.
Common bypass scenarios:
- mv credentials.json safe.json (rename to bypass read protection)
- cp .env .env.backup (copy sensitive files)
- cat id_rsa (read via bash instead of Read tool)
- rm secrets.txt (delete sensitive files)

To prevent these bypasses, ALL bash commands referencing sensitive filenames
are blocked, regardless of the operation.

Sensitive file patterns include:
- Environment files: .env, .env.* (except .env.example, .env.template, etc.)
- Credentials: credentials.json, secrets.*, *.key, *.pem
- Private keys: id_rsa, id_ed25519, *.key
- Cloud credentials: .aws/credentials, .kube/config
- Shell configs: .bashrc, .zshrc

If you need to perform operations on sensitive files:
1. Ask the user to perform the operation manually
2. Explain why you need access to the sensitive file
3. User can execute commands directly in their terminal
4. For reading files, explain what information you need without accessing the file

This protection ensures sensitive files are never exposed through autonomous
AI operations, even via indirect command-line access.
""", file=sys.stderr)
        sys.exit(2)

    # Command is safe - allow it
    sys.exit(0)


if __name__ == '__main__':
    main()
