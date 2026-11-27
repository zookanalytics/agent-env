#!/usr/bin/env bash
#
# enforce-commit-skill.sh
#
# PreToolUse hook for Bash commands that ensures the git-commit skill
# workflow is followed before any git commit.
#
# The state file lives in /tmp keyed by repo path hash, avoiding writes
# to .claude/ (which triggers permission prompts) and keeping it out of
# the repo tree entirely.
#
# Exit codes:
#   0 - Command is allowed
#   2 - Command is blocked (provides feedback to Claude)

set -euo pipefail

# Read JSON input from stdin
input=$(cat)

# Extract tool name and command from JSON
tool_name=$(echo "$input" | jq -r '.tool_name // ""')
command=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only process shell commands (Bash for Claude, run_shell_command for Gemini)
if [[ "$tool_name" != "Bash" && "$tool_name" != "run_shell_command" ]]; then
    exit 0
fi

# Match only invocations where `commit` is git's subcommand.
#
# GIT_TAIL: optional VAR=value assignments, a path to git (/usr/bin/git),
#   then only git global options before `commit`:
#   -C <path>, -c <k=v>, --git-dir/--work-tree/--namespace/--config-env <v>
#   (or =<v>), and bare flags such as --no-pager / -p.
#   `commit` must be a whole word, so commit-tree / commit.gpgsign don't match.
# ARG: a shell word: any mix of "..." / '...' / \x / $(...) (one level of
#   nesting) / `...` segments and plain characters.
#
# Two views are counted and the larger count wins:
#   raw text      - shell operator boundaries only (^ && || ; | ( $( { `),
#                   so an apostrophe in prose can't hide a commit
#   UNQUOTED text - quoted strings -> Q and # comments removed; keyword and
#                   prefix-command boundaries (do, then, sudo -u x, timeout 60,
#                   env -i, ...) are also allowed, since quoted prose such as
#                   "now do git commit" is gone
#
# Matches:        git commit, git -C "$(pwd)" commit, { git commit; },
#                 sudo -u bob git commit
# Does NOT match: git log --grep commit, git config commit.template,
#                 echo "git commit", echo "now do git commit"
ARG=$(cat <<'RE'
(?:"(?:[^"\\]|\\.)*"|'[^']*'|\\.|\$\((?:[^()]|\([^()]*\))*\)|`[^`]*`|[^\s;|&()"'\\`])+
RE
)
OP_BOUNDARY=$(cat <<'RE'
(?:^|&&|\|\||;|\||\$\(|\(|\{|!|`)
RE
)
KW_BOUNDARY=$(cat <<'RE'
\b(?:then|do|else|time|exec|env|command|sudo|nice|nohup|timeout|xargs|watch|stdbuf|ionice)(?:\s+(?:-\S+|\d\S*|\w+=\S*)(?:\s+(?!git\b)[^-\s;|&]\S*)?)*
RE
)
GIT_TAIL="\s*(?:\w+=${ARG}\s+)*(?:\S*/)?git(?:\s+(?:-[Cc]\s+${ARG}|--(?:git-dir|work-tree|namespace|config-env)(?:=${ARG}|\s+${ARG})|-[^\s;|&()]+))*\s+commit(?=\s|$|[;|&)\`])"
RAW_COMMIT="${OP_BOUNDARY}${GIT_TAIL}"
FULL_COMMIT="(?:${OP_BOUNDARY}|${KW_BOUNDARY})${GIT_TAIL}"

# Quoted strings -> Q, then drop # comments (a # at line start or after
# whitespace or an operator)
unquoted=$(printf '%s\n' "$command" \
    | sed -E "s/\"([^\"\\\\]|\\\\.)*\"/Q/g; s/'[^']*'/Q/g; s/(^|[[:space:];|&(])#.*/\\1/")

# `|| true`: grep exits 1 on no match, which pipefail + set -e would turn
# into a non-blocking hook failure
count() { printf '%s\n' "$1" | { grep -oP "$2" || true; } | wc -l; }

raw_count=$(count "$command" "$RAW_COMMIT")
full_count=$(count "$unquoted" "$FULL_COMMIT")
commit_count=$(( raw_count > full_count ? raw_count : full_count ))
if [[ $commit_count -eq 0 ]]; then
    exit 0
fi

# Allow git commit --amend (special case for pre-commit hook fixes), but
# only when EVERY commit in the command is an amend. Counted on the
# unquoted, comment-free text so `-m "... --amend"` and `# --amend` don't count.
amend_count=$(count "$unquoted" "${FULL_COMMIT}[^;|&\n]*\s--amend\b")
if [[ $amend_count -ge $commit_count ]]; then
    exit 0
fi

# Get git repository root
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "Warning: Not in a git repository, skipping commit validation" >&2
    exit 0
}

# State file in /tmp, keyed by repo path hash
REPO_HASH=$(echo -n "$GIT_ROOT" | md5sum | cut -d' ' -f1)
STATE_FILE="/tmp/.commit-state-${REPO_HASH}"

# Check if state file exists
if [[ ! -f "$STATE_FILE" ]]; then
    cat >&2 <<EOF
🚫 Commit blocked - git-commit skill not followed

You MUST use the 'git-commit' skill before committing.

Required workflow:
1. Use Skill tool: Skill(git-commit)
2. Follow ALL checklist steps:
   - Run quality checks
   - Review changes with 'git diff'
   - Stage files with 'git add <files>'
   - Preview staged changes with 'git diff --staged'
   - Touch state file: $STATE_FILE
   - Create commit

Never skip this workflow - even for "simple" changes.
EOF
    exit 2
fi

# Verify state file is recent (within last 5 minutes)
# Note: md5sum and stat -c are Linux-specific; this hook runs in the container image
file_age=$(($(date +%s) - $(stat -c %Y "$STATE_FILE")))

if [[ $file_age -gt 300 ]]; then
    cat >&2 <<EOF
🚫 Commit blocked - stale commit state

The commit state file is older than 5 minutes.

Please re-run the 'git-commit' skill to ensure fresh validation
before committing.

Run: Skill(git-commit)
EOF
    rm -f "$STATE_FILE"
    exit 2
fi

# Allow commit to proceed
exit 0
