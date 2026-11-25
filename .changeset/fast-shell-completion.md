---
"@zookanalytics/agent-env": patch
---

Make `agent-env completion <shell>` fast enough to `eval` on every shell start: ~10x faster (about 280 ms → 30 ms, essentially bare Node startup). The bin entry now prints a pre-generated script instead of loading the CLI; the output is byte-identical to before.

- The completion scripts also ship as static files (`completions/_agent-env` for zsh, `completions/agent-env.bash` for bash) that can be `source`d or added to `fpath` without spawning a process. See "Shell Completion" in the README.
- Other non-interactive commands (`--version`, `list --json`, `path`, …) start roughly 3x faster because ink/react are now loaded only by commands that render a TUI.
