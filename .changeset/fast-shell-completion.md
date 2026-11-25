---
"@zookanalytics/agent-env": patch
---

Make `agent-env completion <shell>` fast enough to `eval` on every shell start: ~10x faster (about 280 ms → 30 ms, essentially bare Node startup). The bin entry now prints a pre-generated script instead of loading the CLI; bash output is unchanged.

- The completion scripts also ship as static files (`completions/_agent-env` for zsh, `completions/agent-env.bash` for bash) that can be `source`d or added to `fpath` without spawning a process. See "Shell Completion" in the README.
- The zsh script now completes on the first Tab when autoloaded from `fpath` (previously the first Tab only loaded it), and also handles `aecd` there.
- Other non-interactive commands (`--version`, `list --json`, `path`, …) start roughly 3x faster because ink/react are now loaded only by commands that render a TUI.
