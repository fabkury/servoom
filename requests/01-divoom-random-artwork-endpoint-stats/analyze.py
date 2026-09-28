"""Analyse samples.jsonl and write report.md next to it.

Per endpoint: latency, items per call, within-call duplicates, distinct items and
their frequencies, pool-size estimates (Chao1, uniform-model estimate, discovery
curve, Good-Turing coverage), uniformity (chi-square), within-call order consistency,
consecutive-call overlap (caching check), and item attributes.

Run from anywhere:  python requests/01-.../analyze.py
"""
import datetime as dt
import itertools
import json
import math
import os
import random
import statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples.jsonl")
REPORT = os.path.join(HERE, "report.md")

recs = [json.loads(line) for line in open(SAMPLES, encoding="utf-8")]


def items_of(rec):
    """Return list of (key, attrs) for one response, or None on error."""
    resp = rec.get("resp")
    if resp is None or resp.get("ReturnCode") != 0:
        return None
    if "TagList" in resp:
        return [(f'{t["TagType"]}:{t["TagName"]}',
                 {"TagType": t["TagType"], "TagName": t["TagName"]})
                for t in resp["TagList"]]
    if "ExpertList" in resp:
        return [(e["ExpertUserId"],
                 {"NickName": e["NickName"], "Level": e["Level"],
                  "Country": e["CountryISOCode"], "Title": e.get("PixelAmbName", "")})
                for e in resp["ExpertList"]]
    return None


def chi2_sf(x, k):
    """Upper tail of chi-square with k dof (Wilson-Hilferty normal approximation)."""
    if k <= 0:
        return float("nan")
    z = ((x / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return 0.5 * math.erfc(z / math.sqrt(2))


def uniform_model_N(k, n_calls, distinct):
    """Pool size N whose expected number of distinct items after n_calls uniform
    draws of k items (no replacement within a call) equals the observed count:
    E[distinct] = N * (1 - (1 - k/N)^n)."""
    if distinct < k or k == 0:
        return float("nan")
    lo = float(max(distinct, k))

    def f(N):
        return N * (1 - (1 - k / N) ** n_calls) - distinct

    if f(lo) >= 0:
        return lo  # every call already spans the whole pool
    hi = lo
    while f(hi) < 0:
        hi *= 2
        if hi > 1e9:
            return float("inf")
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def md_escape(s):
    return str(s).replace("|", "\\|")


out = []
w = out.append
fmt = lambda t: dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
w("# Divoom random-sampler endpoints: statistical report\n")
w(f"Source: `samples.jsonl`, {len(recs)} requests, sampled from {fmt(recs[0]['t'])} to "
  f"{fmt(recs[-1]['t'])} local time, one request per second, alternating the two "
  f"endpoints, logged in as the throwaway test account.\n")

by_ep = defaultdict(list)
for r in recs:
    by_ep[r["ep"]].append(r)

for ep, rs in by_ep.items():
    is_tag = ep.endswith("GetHotTag")
    w(f"\n## `{ep}`\n")
    calls = [(r, items_of(r)) for r in rs]
    errors = [r for r, it in calls if it is None]
    good = [(r, it) for r, it in calls if it is not None]
    lat = sorted(r["ms"] for r in rs if "ms" in r)

    w("### Transport\n")
    w("| calls | failed | median ms | p95 ms | max ms |\n|---|---|---|---|---|")
    w(f"| {len(rs)} | {len(errors)} | {lat[len(lat) // 2] if lat else '-'} | "
      f"{lat[int(len(lat) * 0.95)] if lat else '-'} | {lat[-1] if lat else '-'} |\n")
    if errors:
        codes = Counter(str((r.get('resp') or {}).get('ReturnCode', r.get('error'))) for r in errors)
        w(f"Failure kinds: {dict(codes)}\n")

    sizes = Counter(len(it) for _, it in good)
    dup_calls = sum(1 for _, it in good if len(set(key for key, _ in it)) < len(it))
    w("### Within a call\n")
    w(f"Items per call: {dict(sizes)}. Calls containing the same item twice: "
      f"{dup_calls} of {len(good)}.\n")

    k = max(sizes) if sizes else 0
    n_calls = len(good)
    n_draws = sum(len(it) for _, it in good)
    freq = Counter()
    pos_freq = defaultdict(Counter)
    attrs = {}
    first_seen = {}
    for idx, (r, it) in enumerate(good):
        for p, (key, a) in enumerate(it):
            freq[key] += 1
            pos_freq[key][p] += 1
            attrs[key] = a
            first_seen.setdefault(key, idx)
    S = len(freq)
    fof = Counter(freq.values())
    f1, f2 = fof.get(1, 0), fof.get(2, 0)
    chao1 = S + (f1 * f1 / (2 * f2) if f2 else f1 * (f1 - 1) / 2)
    coverage = 1 - f1 / n_draws if n_draws else float("nan")
    N_model = uniform_model_N(k, n_calls, S)

    w("### Pool size\n")
    w("| draws | distinct items | seen once | seen twice | Good-Turing coverage | "
      "Chao1 estimate | uniform-model estimate |\n|---|---|---|---|---|---|---|")
    w(f"| {n_draws} | {S} | {f1} | {f2} | {coverage:.4f} | {chao1:.1f} | {N_model:.1f} |\n")
    checkpoints = sorted(set(c for c in [1, 2, 3, 5, 10, 20, 50, 100, 200, 400, 600, 800, n_calls]
                             if 0 < c <= n_calls))
    seen = set()
    curve = {}
    for idx, (_, it) in enumerate(good, start=1):
        seen.update(key for key, _ in it)
        if idx in checkpoints:
            curve[idx] = len(seen)
    w("Discovery curve (distinct items after n calls):\n")
    w("| calls | " + " | ".join(str(c) for c in checkpoints) + " |")
    w("|---|" + "---|" * len(checkpoints))
    w("| distinct | " + " | ".join(str(curve[c]) for c in checkpoints) + " |")
    last_new = max(first_seen.values()) + 1 if first_seen else 0
    w(f"\nLast new item appeared in call {last_new} of {n_calls}.\n")

    # pool stability over time: did any item vanish or appear mid-run?
    last_seen = {}
    for idx, (_, it) in enumerate(good):
        for key, _ in it:
            last_seen[key] = idx
    half = n_calls // 2
    freq_a = Counter(key for _, it in good[:half] for key, _ in it)
    freq_b = Counter(key for _, it in good[half:] for key, _ in it)
    # expected gap between sightings of one item under uniform k-of-S sampling
    p_item = k / S if S else 0
    gap_99 = math.log(0.01) / math.log(1 - p_item) if 0 < p_item < 1 else 0
    late_first = [key for key, i0 in first_seen.items() if i0 > gap_99]
    early_last = [key for key, i1 in last_seen.items() if n_calls - 1 - i1 > gap_99]
    w("Pool stability: with a uniform draw each item has a 99% chance of showing up within "
      f"{gap_99:.0f} calls. Items first seen later than that: {len(late_first)}; items last "
      f"seen earlier than that before the end: {len(early_last)}.")
    if late_first or early_last:
        w("Suspicious items: " + ", ".join(
            f"`{attrs[x].get('TagName', attrs[x].get('NickName')) or '(empty)'}` "
            f"(first call {first_seen[x] + 1}, last call {last_seen[x] + 1})"
            for x in late_first + early_last))
    both = [key for key in freq if freq_a[key] and freq_b[key]]
    if both and half:
        chi_ab = 0.0
        for key in freq:
            ea = freq[key] * half / n_calls
            eb = freq[key] - ea
            if ea > 0 and eb > 0:
                chi_ab += (freq_a[key] - ea) ** 2 / ea + (freq_b[key] - eb) ** 2 / eb
        w(f"First half vs second half of the run: chi-square = {chi_ab:.1f} on {S - 1} dof, "
          f"p = {chi2_sf(chi_ab, S - 1):.3g} (large p = same frequencies in both halves).")
    w("")

    w("### Distribution over items\n")
    exp = n_draws / S if S else 0
    chi2 = sum((c - exp) ** 2 / exp for c in freq.values()) if exp else 0
    p = chi2_sf(chi2, S - 1)
    counts = sorted(freq.values())
    w(f"Uniform hypothesis over the {S} observed items: expected {exp:.1f} draws each, "
      f"observed min {counts[0]}, median {counts[len(counts) // 2]}, max {counts[-1]}; "
      f"chi-square = {chi2:.1f} on {S - 1} dof, p = {p:.3g}.\n")
    w("Per-item frequencies (sorted by count):\n")
    if is_tag:
        w("| tag | TagType | count | share | ratio to uniform | first-position share |\n"
          "|---|---|---|---|---|---|")
        for key, c in freq.most_common():
            a = attrs[key]
            w(f"| `{a['TagName'] or '(empty)'}` | {a['TagType']} | {c} | {c / n_draws:.3%} | "
              f"{c / exp:.2f} | {pos_freq[key][0] / c:.0%} |")
    else:
        w("| user id | nickname | level | country | count | share | ratio to uniform | "
          "first-position share |\n|---|---|---|---|---|---|---|---|")
        for key, c in freq.most_common():
            a = attrs[key]
            w(f"| {key} | {md_escape(a['NickName'])} | {a['Level']} | {a['Country']} | {c} | "
              f"{c / n_draws:.3%} | {c / exp:.2f} | {pos_freq[key][0] / c:.0%} |")
    w("")

    if is_tag:
        tt = Counter(attrs[key]["TagType"] for key in freq)
        ttd = Counter()
        for key, c in freq.items():
            ttd[attrs[key]["TagType"]] += c
        w(f"TagType among distinct tags: {dict(sorted(tt.items()))}; among draws: "
          f"{dict(sorted(ttd.items()))}.\n")
        w("Position-wise TagType mix:\n")
        pt = defaultdict(Counter)
        for _, it in good:
            for p_, (key, a) in enumerate(it):
                pt[p_][a["TagType"]] += 1
        types = sorted(ttd)
        w("| position | " + " | ".join(f"type {t}" for t in types) + " |")
        w("|---|" + "---|" * len(types))
        for p_ in sorted(pt):
            w(f"| {p_ + 1} | " + " | ".join(str(pt[p_][t]) for t in types) + " |")
        w("")
    else:
        titles = Counter(attrs[key]["Title"] for key in freq)
        countries = Counter(attrs[key]["Country"] for key in freq)
        levels = sorted(attrs[key]["Level"] for key in freq)
        w(f"Titles among distinct experts: {dict(titles)}.\n")
        w(f"Countries among distinct experts: {dict(countries.most_common())}.\n")
        w(f"Levels: min {levels[0]}, median {levels[len(levels) // 2]}, max {levels[-1]}.\n")

    # pairwise co-occurrence: under a uniform random k-subset every pair of the S items
    # co-occurs with probability k(k-1)/(S(S-1)) per call
    if S > k > 1 and n_calls > 0:
        co = Counter()
        for _, it in good:
            keys = sorted(set(key for key, _ in it))
            for a, b in itertools.combinations(keys, 2):
                co[(a, b)] += 1
        n_pairs = S * (S - 1) // 2
        exp_pair = n_calls * k * (k - 1) / (S * (S - 1))
        chi_pair = sum((co.get(pr, 0) - exp_pair) ** 2 / exp_pair
                       for pr in itertools.combinations(sorted(freq), 2))
        never = n_pairs - len(co)
        top = co.most_common(3)
        name = lambda x: attrs[x].get("TagName", attrs[x].get("NickName")) or "(empty)"
        w(f"Pairwise co-occurrence over the {n_pairs} item pairs: expected {exp_pair:.1f} joint "
          f"appearances per pair, pairs never seen together {never}, most frequent pair "
          f"{' + '.join(f'`{name(x)}`' for x in top[0][0])} at {top[0][1]}; chi-square = "
          f"{chi_pair:.1f} on {n_pairs - 1} dof, p = {chi2_sf(chi_pair, n_pairs - 1):.3g} "
          "(tests that items are drawn independently of each other).\n")

    w("### Order within a call\n")
    pair_order = defaultdict(Counter)
    for _, it in good:
        keys = [key for key, _ in it]
        for i, j in itertools.combinations(range(len(keys)), 2):
            a, b = keys[i], keys[j]
            if a != b:
                pair_order[frozenset((a, b))][(a, b)] += 1
    pairs = len(pair_order)
    inconsistent = sum(1 for d in pair_order.values() if len(d) > 1)
    w(f"Unordered item pairs seen together: {pairs}; pairs that appeared in both orders: "
      f"{inconsistent}.")
    if pairs and inconsistent == 0:
        before = defaultdict(set)
        for d in pair_order.values():
            (a, b), = d.keys()
            before[b].add(a)
        order = []
        remaining = set(freq)
        while remaining:
            ready = sorted(x for x in remaining if not (before[x] & remaining))
            if not ready:
                break
            order.extend(ready)
            remaining -= set(ready)
        w("Every co-occurring pair kept the same relative order, so the endpoint returns a "
          "random subset of a fixed underlying sequence. Inferred sequence (ties broken "
          "alphabetically):\n")
        if is_tag:
            w(", ".join(f"`{attrs[x]['TagName'] or '(empty)'}`" for x in order))
            names = [attrs[x]["TagName"].lower() for x in order]
            w(f"\nSequence alphabetical? {names == sorted(names)}.")
        else:
            w(", ".join(f"{md_escape(attrs[x]['NickName'])} ({x}, L{attrs[x]['Level']})"
                        for x in order))
            ids = [int(x) for x in order]
            lv = [attrs[x]["Level"] for x in order]
            w(f"\nSequence sorted by user id ascending? {ids == sorted(ids)}. "
              f"By level descending? {lv == sorted(lv, reverse=True)}.")
    elif pairs:
        w(f"{inconsistent / pairs:.1%} of pairs were seen in both orders, so the order "
          "within a call carries no fixed structure.")
    w("")

    w("### Dependence between calls\n")
    sets = [set(key for key, _ in it) for _, it in good]
    consec = [jaccard(sets[i], sets[i + 1]) for i in range(len(sets) - 1)]
    random.seed(1)
    rand = [jaccard(*random.sample(sets, 2)) for _ in range(min(5000, len(sets) * 3))] if len(sets) > 1 else [0]
    exact_repeat = sum(1 for i in range(len(sets) - 1) if sets[i] == sets[i + 1])
    exp_inter = k * k / S if S else 0
    exp_jac = exp_inter / (2 * k - exp_inter) if k else 0
    w(f"Mean Jaccard overlap: consecutive calls {st.mean(consec):.4f}, random call pairs "
      f"{st.mean(rand):.4f}; identical consecutive sets: {exact_repeat}. For uniform "
      f"{k}-subsets of {S} items the expected overlap is about {exp_jac:.4f}.\n")
    seqs = [tuple(key for key, _ in it) for _, it in good]
    w(f"Distinct ordered responses: {len(set(seqs))} of {len(seqs)} calls.\n")

open(REPORT, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"wrote {REPORT}: {len(recs)} records")
