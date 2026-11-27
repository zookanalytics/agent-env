---
"@zookanalytics/agent-env": patch
---

Share one Claude Code login across all instances. The devcontainer now sets `CLAUDE_SECURESTORAGE_CONFIG_DIR=/shared-data/claude/secure-storage`, so every container reads, refreshes, and locks the same credentials file instead of a symlink that Claude replaced on each token refresh. Existing credentials are migrated automatically on first start (the most recently refreshed one wins); new instances no longer ask you to log in.
