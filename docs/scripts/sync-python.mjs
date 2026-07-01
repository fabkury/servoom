// Copy the canonical Python decoder modules from servoom/ into docs/src/python/ so the
// browser (Pyodide) tool and the Python library share ONE source of truth.
//
// The generated files are committed. A predev/prebuild hook regenerates them, and CI runs
// this script then `git diff --exit-code docs/src/python` to fail on drift.
//
// Node-only (no Python needed at build time). Output is LF-normalized so it is identical
// on Windows and Linux.

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const srcDir = join(repoRoot, 'servoom');
const outDir = join(repoRoot, 'docs', 'src', 'python');

// Modules the browser decoder needs. They are loaded flat into the Pyodide FS, which is
// why pixel_bean_decoder.py uses a try/except import for pixel_bean and stdlib logging.
const MODULES = ['pixel_bean.py', 'pixel_bean_decoder.py'];

function header(name) {
  return [
    '# AUTO-GENERATED FILE — DO NOT EDIT.',
    `# Copied verbatim from servoom/${name} by docs/scripts/sync-python.mjs.`,
    '# Edit the source in servoom/, then run:  node docs/scripts/sync-python.mjs',
    '',
    '',
  ].join('\n');
}

let changed = 0;
for (const name of MODULES) {
  const src = readFileSync(join(srcDir, name), 'utf8').replace(/\r\n/g, '\n');
  const out = (header(name) + src).replace(/\r\n/g, '\n');
  const dest = join(outDir, name);
  let prev = null;
  try {
    prev = readFileSync(dest, 'utf8');
  } catch {
    /* missing */
  }
  if (prev !== out) {
    writeFileSync(dest, out);
    changed += 1;
    console.log(`synced   ${name}`);
  } else {
    console.log(`up-to-date ${name}`);
  }
}
console.log(changed ? `sync-python: ${changed} file(s) updated` : 'sync-python: already in sync');
