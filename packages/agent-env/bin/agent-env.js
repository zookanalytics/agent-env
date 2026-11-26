#!/usr/bin/env node
// Fast path for `agent-env completion <shell>`.
//
// `eval "$(agent-env completion zsh)"` runs on every new shell, so this must not
// load the CLI bundle (commander, execa, ...). The completion scripts are static
// text, generated at build time from the real CLI by scripts/generate-completions.mjs,
// so we just print the pre-generated file. Anything else — including a missing
// file, an unsupported shell, or extra args like --help — falls through to the CLI.
import { readFileSync } from 'node:fs';

const COMPLETION_FILES = { bash: 'agent-env.bash', zsh: '_agent-env' };

const args = process.argv.slice(2);
let handled = false;

if (args.length === 2 && args[0] === 'completion' && Object.hasOwn(COMPLETION_FILES, args[1])) {
  try {
    const file = new URL(`../completions/${COMPLETION_FILES[args[1]]}`, import.meta.url);
    process.stdout.write(readFileSync(file));
    handled = true;
  } catch {
    // Pre-generated script unavailable — let the full CLI generate it.
  }
}

if (!handled) {
  await import('../dist/cli.js');
}
