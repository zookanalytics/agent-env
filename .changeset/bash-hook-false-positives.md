---
"@zookanalytics/agent-env": patch
---

Stop the image's Bash safety hooks from blocking valid commands. The sensitive-filename hook no longer rejects heredoc bodies or `#` comments that contain an apostrophe (e.g. `gh pr create --body-file - <<'EOF'`), and it closes several quoting bypasses. The git-commit enforcement hook now only triggers for the actual `git commit` subcommand, so `git log --grep commit`, `git config commit.template` and similar commands are no longer blocked. `search-history --zsh` now exits 0 when it finds matches, instead of 1.
