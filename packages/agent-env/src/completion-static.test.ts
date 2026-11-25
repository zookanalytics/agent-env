/**
 * Guards the `agent-env completion <shell>` fast path.
 *
 * bin/agent-env.js prints the pre-generated files in completions/ instead of
 * loading the CLI. Those files are generated from the CLI at build time
 * (scripts/generate-completions.mjs), so all three of these must stay
 * byte-identical:
 *   1. what the full CLI generates from source
 *   2. the committed completions/ file (also usable via fpath / source)
 *   3. what the bin fast path prints
 */
import { execa } from 'execa';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const packageRoot = join(import.meta.dirname, '..');
const binPath = join(packageRoot, 'bin', 'agent-env.js');

const SHELLS = [
  { shell: 'bash', file: 'agent-env.bash' },
  { shell: 'zsh', file: '_agent-env' },
] as const;

/** Run and capture stdout exactly as emitted (no trailing-newline stripping). */
async function stdoutOf(command: string, args: string[]): Promise<string> {
  const result = await execa(command, args, { cwd: packageRoot, stripFinalNewline: false });
  return result.stdout;
}

describe.each(SHELLS)('static $shell completion script', ({ shell, file }) => {
  const staticPath = join(packageRoot, 'completions', file);

  it('matches what the full CLI generates from source', async () => {
    const fromSource = await stdoutOf('tsx', [join('src', 'cli.ts'), 'completion', shell]);
    const committed = await readFile(staticPath, 'utf8');

    // If this fails, a command changed: run `pnpm build` and commit completions/.
    expect(committed).toBe(fromSource);
  });

  it('is printed byte-for-byte by the bin fast path', async () => {
    const fromBin = await stdoutOf('node', [binPath, 'completion', shell]);
    const committed = await readFile(staticPath, 'utf8');

    expect(fromBin).toBe(committed);
  });
});

describe('bin fast path', () => {
  /** Whether running the bin with these args loads the main CLI bundle. */
  async function loadsCliBundle(args: string[]): Promise<boolean> {
    const result = await execa('node', [binPath, ...args], {
      cwd: packageRoot,
      env: { ...process.env, NODE_DEBUG: 'esm' }, // traces every ESM load to stderr
      reject: false,
    });
    return result.stderr.includes('dist/cli.js');
  }

  it('does not load the CLI bundle for completion', async () => {
    expect(await loadsCliBundle(['completion', 'zsh'])).toBe(false);
    expect(await loadsCliBundle(['completion', 'bash'])).toBe(false);
  });

  it('falls through to the full CLI for everything else', async () => {
    // Also the positive control for the trace-based detection above.
    expect(await loadsCliBundle(['completion', 'fish'])).toBe(true);
    expect(await loadsCliBundle(['completion', '--help'])).toBe(true);
  });
});
