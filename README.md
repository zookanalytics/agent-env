# agent-env

[![Publish](https://github.com/ZookAnalytics/agent-env/actions/workflows/publish.yml/badge.svg?branch=main)](https://github.com/ZookAnalytics/agent-env/actions/workflows/publish.yml)
[![npm version](https://img.shields.io/npm/v/@zookanalytics/agent-env)](https://www.npmjs.com/package/@zookanalytics/agent-env)

Monorepo for agent-env: a CLI for creating isolated, AI-ready development environments, plus the devcontainer image those environments run on.

## Packages

| Package | Description |
|---------|-------------|
| [`@zookanalytics/agent-env`](packages/agent-env) | CLI for creating isolated, AI-ready development environments |

## Layout

- `packages/agent-env` — the agent-env CLI
- `packages/shared` — internal utilities used by agent-env
- `image/` — the devcontainer image (Dockerfile, firewall, Claude Code safety hooks, setup scripts)

## Development

```bash
pnpm install
pnpm -r build
pnpm -r test:run
```
