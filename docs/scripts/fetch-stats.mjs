// Downloads the published aggregates of the statistics pipeline (the data/ folder of
// the public servoom-stats repository) into public/stats/data/, so the site serves
// pages and data from one origin. Runs before every dev server start and build.
//
// In a deploy build (Cloudflare Pages or CI) a failed download fails the build, which
// keeps the previous deploy online. Locally it only warns.
import { execFileSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = process.env.STATS_REPO ?? 'fabkury/servoom-stats';
const URL = `https://codeload.github.com/${REPO}/tar.gz/refs/heads/main`;
const dest = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'stats', 'data');
const strict = Boolean(process.env.CF_PAGES || process.env.CI);

try {
  const res = await fetch(URL);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${URL}`);
  const tmp = mkdtempSync(join(tmpdir(), 'servoom-stats-'));
  const tarball = join(tmp, 'stats.tar.gz');
  writeFileSync(tarball, Buffer.from(await res.arrayBuffer()));
  execFileSync('tar', ['-xzf', 'stats.tar.gz'], { cwd: tmp }); // relative name: GNU tar reads "C:" as a host
  const root = readdirSync(tmp).find((n) => n !== 'stats.tar.gz');
  const data = join(tmp, root, 'data');
  if (!existsSync(data)) throw new Error('the archive has no data/ folder');
  rmSync(dest, { recursive: true, force: true });
  mkdirSync(dest, { recursive: true });
  cpSync(data, dest, { recursive: true });
  rmSync(tmp, { recursive: true, force: true });
  console.log(`fetch-stats: copied data/ from ${REPO}`);
} catch (err) {
  console.error(`fetch-stats: ${err.message}`);
  if (strict) process.exit(1);
  console.error('fetch-stats: continuing without fresh data (local run)');
}
