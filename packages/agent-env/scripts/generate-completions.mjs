#!/usr/bin/env node
// Generates the static completion scripts in completions/ from the built CLI.
//
// Runs as part of `pnpm build` (after tsup). The output is captured from the full
// CLI (dist/cli.js, bypassing the bin fast path), so the shipped files are
// byte-identical to what `agent-env completion <shell>` generates — bin/agent-env.js
// prints these files directly instead of loading the CLI.
//
// The files are committed so they can be sourced/fpath'd straight from a checkout;
// src/completion-static.test.ts fails if they drift from the source.
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const TARGETS = { bash: 'agent-env.bash', zsh: '_agent-env' };

const cli = fileURLToPath(new URL('../dist/cli.js', import.meta.url));
const outDir = new URL('../completions/', import.meta.url);
mkdirSync(outDir, { recursive: true });

for (const [shell, fileName] of Object.entries(TARGETS)) {
  const script = execFileSync(process.execPath, [cli, 'completion', shell]);
  writeFileSync(new URL(fileName, outDir), script);
  console.log(`completions/${fileName} (${script.length} bytes)`);
}
