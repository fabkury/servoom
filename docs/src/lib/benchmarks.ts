// Community percentiles published by the statistics pipeline (stats/data/daily/
// benchmarks.json). Used to show where one of the user's own artworks falls among
// comparable uploads. Everything is computed here in the browser.

interface BenchmarkRow {
  size: number;
  group: string;
  age: string;
  n: number;
  likes: number[];
  views: number[];
}

export interface Benchmarks {
  quantiles: number[];
  rows: BenchmarkRow[];
}

export interface ArtworkLike {
  LikeCnt: number;
  WatchCnt: number;
  Date: number;
  Classify: number;
  [key: string]: unknown;
}

const PHOTO_CATEGORY = 12;

export async function loadBenchmarks(): Promise<Benchmarks | null> {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}stats/data/daily/benchmarks.json`);
    return res.ok ? ((await res.json()) as Benchmarks) : null;
  } catch {
    return null;
  }
}

/**
 * Share of comparable community uploads (same canvas size, curation tier and age band)
 * that this artwork's like count is above, as a whole percentage; null when unknown.
 */
export function likePercentile(b: Benchmarks | null, item: ArtworkLike): number | null {
  if (!b) return null;
  const ageDays = (Date.now() / 1000 - item.Date) / 86400;
  if (ageDays < 7) return null; // too young to compare
  const group =
    item.Classify === PHOTO_CATEGORY ? 'photo' : item.IsAddRecommend === 1 ? 'rec' : item.IsAddNew === 1 ? 'new' : 'none';
  const age = ageDays <= 60 ? '7-60 days' : 'over 60 days';
  const row = b.rows.find((r) => r.size === Number(item.FileSize) && r.group === group && r.age === age);
  if (!row) return null;
  const q = b.quantiles;
  const v = row.likes;
  if (item.LikeCnt <= v[0]) return Math.round((q[0] * 100 * item.LikeCnt) / Math.max(v[0], 1));
  for (let i = 1; i < v.length; i += 1) {
    if (item.LikeCnt <= v[i]) {
      const f = v[i] === v[i - 1] ? 1 : (item.LikeCnt - v[i - 1]) / (v[i] - v[i - 1]);
      return Math.round((q[i - 1] + f * (q[i] - q[i - 1])) * 100);
    }
  }
  return 99;
}
