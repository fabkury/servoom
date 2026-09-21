#!/usr/bin/env python
"""Reference-corpus tool: build, fetch and baseline the Divoom artwork corpus.

The corpus is the shared test oracle for every servoom vertical. The payload files under
``corpus/files/`` are git-ignored (they are Divoom users' artworks); what the repo tracks is

* ``manifest.json`` -- every file's gallery id, cloud file id, format byte, size and SHA-256,
  so anyone with credentials can re-download the exact same set, and
* ``baseline.json`` -- what the *Python* decoders produce for each file (frame count, canvas,
  speed and a SHA-256 over all decoded RGB bytes). The C library is tested against it.

Commands (run from anywhere; credentials come from ``SERVOOM_EMAIL`` + ``SERVOOM_PASSWORD``
or ``SERVOOM_MD5_PASSWORD``, or ``python/credentials.py``):

    python corpus/corpus.py discover [--target FMT=N ...] [--max-scan N]
        Scan gallery feeds, download artworks (and their layer files) and keep them until
        each format's target count is met. Extends manifest.json.
    python corpus/corpus.py import-dir DIR
        Add local ``<galleryid>_<name>.dat`` files (e.g. an earlier bulk download).
    python corpus/corpus.py fetch
        Download every manifest entry missing from corpus/files/ (verifies SHA-256).
    python corpus/corpus.py baseline
        Decode every file with the Python decoders and write baseline.json.
    python corpus/corpus.py verify
        Check the files on disk against manifest.json.
    python corpus/corpus.py dump PATH [-o DIR]
        Write a file's decoded frames as raw RGB (and .ppm) for debugging.
    python corpus/corpus.py stats
        Print the per-format histogram.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import time
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "python"))

from servoom.layer_file_decoder import LayerFileDecoder  # noqa: E402
from servoom.pixel_bean_decoder import PixelBeanDecoder  # noqa: E402

MANIFEST = HERE / "manifest.json"
BASELINE = HERE / "baseline.json"
FILES = HERE / "files"

LAYER_FORMATS = (0x27, 0x28)
ARTWORK_FORMATS = (9, 17, 18, 26, 31, 41, 42, 43)

# Gallery filters (see python/servoom/gallery_reference.py): FileSize is a bitmask of canvas
# sizes, FileType a GalleryType, Classify a category.
FILE_SIZES = {"16": 1, "32": 2, "64": 4, "128": 16, "256": 32}
FILE_TYPES = {"pic": 0, "anim": 1, "multi_pic": 2, "multi_anim": 3, "all": 5}
CATEGORIES = {"new": 0, "recommend": 18, "top": 14, "character": 3, "nature": 6,
              "creative": 9, "photo": 12, "animal": 32, "person": 33, "food": 35}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> Dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text("utf-8"))
    return {"entries": []}


def save_manifest(m: Dict) -> None:
    m["entries"].sort(key=lambda e: (e["format"], e["gallery_id"], e["kind"]))
    MANIFEST.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n", "utf-8", newline="\n")


def entry_path(fmt: int, gallery_id: int, kind: str) -> str:
    sub = f"layer{fmt:02x}" if kind == "layer" else f"fmt{fmt:02d}"
    return f"files/{sub}/{gallery_id}.dat"


def format_byte(path: Path) -> int:
    with open(path, "rb") as fh:
        b = fh.read(1)
    return b[0] if b else -1


def _client():
    from servoom import DivoomClient
    client = DivoomClient()
    if not client.login():
        sys.exit("Login failed -- corpus discovery/fetch needs working Divoom credentials")
    return client


def _parse_targets(items: List[str], default: int) -> Dict[int, int]:
    targets = {f: default for f in ARTWORK_FORMATS + LAYER_FORMATS}
    for item in items or []:
        k, v = item.split("=")
        targets[int(k, 0)] = int(v)
    return targets


# --------------------------------------------------------------------------- #
# discover / import / fetch
# --------------------------------------------------------------------------- #
def _add_entry(manifest: Dict, index: Dict, *, kind: str, gallery_id: int, file_id: str,
               meta: Dict, tmp: Path) -> Optional[Dict]:
    fmt = format_byte(tmp)
    rel = entry_path(fmt, gallery_id, kind)
    dest = HERE / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), dest)
    entry = {
        "path": rel, "kind": kind, "gallery_id": gallery_id, "file_id": file_id,
        "format": fmt, "bytes": dest.stat().st_size, "sha256": sha256_file(dest),
        "file_name": meta.get("FileName"), "file_size_flag": meta.get("FileSize"),
        "file_type": meta.get("FileType"), "user_id": meta.get("UserId"),
    }
    manifest["entries"].append(entry)
    index[(kind, gallery_id)] = entry
    return entry


def cmd_discover(args) -> int:
    client = _client()
    manifest = load_manifest()
    index = {(e["kind"], e["gallery_id"]): e for e in manifest["entries"]}
    counts = Counter((e["format"] for e in manifest["entries"]))
    targets = _parse_targets(args.target, args.default_target)
    tmp = HERE / "_tmp.dat"

    def need(fmt: int) -> bool:
        return counts[fmt] < targets.get(fmt, 0)

    def done() -> bool:
        return all(not need(f) for f in targets)

    scanned = 0
    combos = [(c, s, t) for c in args.category for s in args.size for t in args.type]
    for cat_name, size_name, type_name in combos:
        if done():
            break
        # Skip combos that can no longer contribute: artworks of this canvas size are
        # already saturated AND we don't need layer files any more.
        page_extra = {"FileSize": FILE_SIZES[size_name], "FileType": FILE_TYPES[type_name]}
        try:
            items = client.fetch_category_files(CATEGORIES[cat_name], limit=args.per_combo,
                                                **page_extra)
        except Exception as exc:  # network hiccup: move on
            print(f"[warn] listing {cat_name}/{size_name}/{type_name} failed: {exc}")
            continue
        kept = 0
        for item in items:
            if done():
                break
            gid = item.get("GalleryId")
            fid = item.get("FileId")
            if not gid or not fid:
                continue
            scanned += 1
            if scanned > args.max_scan:
                break
            if ("artwork", gid) not in index:
                try:
                    client.download_file(fid, str(tmp))
                except Exception as exc:
                    print(f"[warn] download {gid} failed: {exc}")
                    continue
                fmt = format_byte(tmp)
                if need(fmt):
                    _add_entry(manifest, index, kind="artwork", gallery_id=gid, file_id=fid,
                               meta=item, tmp=tmp)
                    counts[fmt] += 1
                    kept += 1
                else:
                    tmp.unlink(missing_ok=True)
            lid = item.get("LayerFileId")
            if lid and ("layer", gid) not in index and (need(0x27) or need(0x28)):
                try:
                    client.download_file(lid, str(tmp))
                except Exception as exc:
                    print(f"[warn] layer download {gid} failed: {exc}")
                    continue
                fmt = format_byte(tmp)
                if fmt in LAYER_FORMATS and need(fmt):
                    _add_entry(manifest, index, kind="layer", gallery_id=gid, file_id=lid,
                               meta=item, tmp=tmp)
                    counts[fmt] += 1
                    kept += 1
                else:
                    tmp.unlink(missing_ok=True)
            time.sleep(args.delay)
        save_manifest(manifest)
        print(f"{cat_name:>9}/{size_name:>3}/{type_name:<10} items={len(items):3d} kept={kept:3d} "
              f"| " + " ".join(f"{f:#04x}:{counts[f]}/{targets[f]}" for f in sorted(targets)))
        if scanned > args.max_scan:
            print("max-scan reached")
            break
    save_manifest(manifest)
    return 0


def cmd_import_dir(args) -> int:
    manifest = load_manifest()
    index = {(e["kind"], e["gallery_id"]): e for e in manifest["entries"]}
    added = 0
    for src in sorted(Path(args.dir).glob("*.dat")):
        stem = src.stem
        gid_str = stem.split("_", 1)[0]
        if not gid_str.isdigit():
            print(f"[skip] {src.name}: no gallery id prefix")
            continue
        gid = int(gid_str)
        fmt = format_byte(src)
        kind = "layer" if fmt in LAYER_FORMATS else "artwork"
        if (kind, gid) in index:
            continue
        rel = entry_path(fmt, gid, kind)
        dest = HERE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        entry = {
            "path": rel, "kind": kind, "gallery_id": gid, "file_id": None, "format": fmt,
            "bytes": dest.stat().st_size, "sha256": sha256_file(dest),
            "file_name": stem.split("_", 1)[1] if "_" in stem else None,
            "file_size_flag": None, "file_type": None, "user_id": None,
        }
        manifest["entries"].append(entry)
        index[(kind, gid)] = entry
        added += 1
    save_manifest(manifest)
    print(f"imported {added} file(s)")
    return 0


def cmd_fetch(args) -> int:
    manifest = load_manifest()
    missing = [e for e in manifest["entries"] if not (HERE / e["path"]).exists()]
    if not missing:
        print("corpus complete")
        return 0
    client = _client()
    ok = bad = 0
    for e in missing:
        dest = HERE / e["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        fid = e.get("file_id")
        if not fid:  # resolve through gallery info (imported entries have no file id)
            info = client.fetch_artwork_info(e["gallery_id"])
            fid = (info or {}).get("LayerFileId" if e["kind"] == "layer" else "FileId")
            if not fid:
                print(f"[fail] {e['path']}: cannot resolve file id")
                bad += 1
                continue
            e["file_id"] = fid
        try:
            client.download_file(fid, str(dest))
        except Exception as exc:
            print(f"[fail] {e['path']}: {exc}")
            bad += 1
            continue
        if sha256_file(dest) != e["sha256"]:
            print(f"[fail] {e['path']}: SHA-256 mismatch (artwork changed on the cloud?)")
            bad += 1
        else:
            ok += 1
        time.sleep(args.delay)
    save_manifest(manifest)
    print(f"fetched {ok} ok, {bad} failed")
    return 1 if bad else 0


def cmd_verify(_args) -> int:
    manifest = load_manifest()
    bad = 0
    for e in manifest["entries"]:
        p = HERE / e["path"]
        if not p.exists():
            print(f"[missing] {e['path']}")
            bad += 1
        elif sha256_file(p) != e["sha256"]:
            print(f"[corrupt] {e['path']}")
            bad += 1
    print(f"{len(manifest['entries'])} entries, {bad} problem(s)")
    return 1 if bad else 0


def cmd_stats(_args) -> int:
    manifest = load_manifest()
    counts = Counter((e["kind"], e["format"]) for e in manifest["entries"])
    total = sum(e["bytes"] for e in manifest["entries"])
    for (kind, fmt), n in sorted(counts.items()):
        print(f"{kind:8s} {fmt:#04x} ({fmt:2d}): {n}")
    print(f"{len(manifest['entries'])} files, {total / 1e6:.1f} MB")
    return 0


# --------------------------------------------------------------------------- #
# baseline (Python oracle)
# --------------------------------------------------------------------------- #
def decode_summary(path: Path) -> Dict:
    """Decode one file; return the baseline record (or an ``error`` record)."""
    fmt = format_byte(path)
    sink = io.StringIO()
    try:
        with redirect_stdout(sink), redirect_stderr(sink):
            if fmt in LAYER_FORMATS:
                layer = LayerFileDecoder.decode_file(str(path))
                comp = hashlib.sha256()
                for i in range(layer.num_frames):
                    comp.update(layer.composite_frame(i).tobytes())
                raw = hashlib.sha256()
                table = hashlib.sha256()
                for i, meta in enumerate(layer.frames_meta):
                    raw.update(layer.frame_layers(i).tobytes())
                    table.update(bytes([meta["num_layers"], meta["flag"]]))
                    for lm in meta["layers"]:
                        table.update(bytes([1 if lm["hidden"] else 0, lm["opacity"]]))
                return {"kind": "layer", "format": fmt, "frames": layer.num_frames,
                        "width": layer.width, "height": layer.height,
                        "total_layers": layer.total_layers, "hash": comp.hexdigest(),
                        "layers_hash": raw.hexdigest(), "table_hash": table.hexdigest()}
            bean = PixelBeanDecoder.decode_file(str(path))
            if bean is None:
                return {"kind": "pixel", "format": fmt, "error": "decoder returned None"}
            h = hashlib.sha256()
            for i in range(bean.total_frames):
                h.update(bean.frames_data[i].tobytes())
            return {"kind": "pixel", "format": fmt, "frames": bean.total_frames,
                    "speed": bean.speed, "width": bean.width, "height": bean.height,
                    "hash": h.hexdigest()}
    except Exception as exc:  # the oracle failed: record it so C must fail too (gracefully)
        return {"kind": "layer" if fmt in LAYER_FORMATS else "pixel", "format": fmt,
                "error": f"{type(exc).__name__}: {exc}"[:200]}


def cmd_baseline(args) -> int:
    manifest = load_manifest()
    baseline = json.loads(BASELINE.read_text("utf-8")) if BASELINE.exists() and not args.rebuild else {}
    n = 0
    for e in manifest["entries"]:
        if e["path"] in baseline and not args.rebuild:
            continue
        p = HERE / e["path"]
        if not p.exists():
            print(f"[missing] {e['path']} (run fetch)")
            continue
        baseline[e["path"]] = decode_summary(p)
        n += 1
        if n % 50 == 0:
            print(f"  {n} decoded...")
    # Drop entries no longer in the manifest.
    known = {e["path"] for e in manifest["entries"]}
    baseline = {k: v for k, v in baseline.items() if k in known}
    BASELINE.write_text(json.dumps(baseline, indent=1, sort_keys=True) + "\n", "utf-8",
                        newline="\n")
    errors = sum(1 for v in baseline.values() if "error" in v)
    print(f"baseline: {len(baseline)} entries ({n} newly decoded), {errors} oracle error(s)")
    return 0


def cmd_dump(args) -> int:
    src = Path(args.path)
    out = Path(args.out or (HERE / "dump" / src.stem))
    out.mkdir(parents=True, exist_ok=True)
    fmt = format_byte(src)
    with redirect_stdout(io.StringIO()):
        if fmt in LAYER_FORMATS:
            layer = LayerFileDecoder.decode_file(str(src))
            frames = [layer.composite_frame(i) for i in range(layer.num_frames)]
            for i in range(layer.num_frames):
                for li in range(layer.frames_meta[i]["num_layers"]):
                    (out / f"layer_{i:03d}_{li:02d}.rgb").write_bytes(layer.frame_layers(i)[li].tobytes())
            w, h = layer.width, layer.height
        else:
            bean = PixelBeanDecoder.decode_file(str(src))
            frames = bean.frames_data
            w, h = bean.width, bean.height
    for i, fr in enumerate(frames):
        data = fr.tobytes()
        (out / f"frame_{i:03d}.rgb").write_bytes(data)
        (out / f"frame_{i:03d}.ppm").write_bytes(f"P6\n{w} {h}\n255\n".encode() + data)
    print(f"wrote {len(frames)} frame(s) ({w}x{h}) to {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover")
    d.add_argument("--target", action="append", help="FMT=N (e.g. 0x1f=40); repeatable")
    d.add_argument("--default-target", type=int, default=40)
    d.add_argument("--max-scan", type=int, default=5000)
    d.add_argument("--per-combo", type=int, default=80)
    d.add_argument("--delay", type=float, default=0.05)
    d.add_argument("--category", nargs="*", default=list(CATEGORIES), choices=list(CATEGORIES))
    d.add_argument("--size", nargs="*", default=list(FILE_SIZES), choices=list(FILE_SIZES))
    d.add_argument("--type", nargs="*", default=["all", "pic", "anim"], choices=list(FILE_TYPES))
    d.set_defaults(func=cmd_discover)

    i = sub.add_parser("import-dir")
    i.add_argument("dir")
    i.set_defaults(func=cmd_import_dir)

    f = sub.add_parser("fetch")
    f.add_argument("--delay", type=float, default=0.05)
    f.set_defaults(func=cmd_fetch)

    b = sub.add_parser("baseline")
    b.add_argument("--rebuild", action="store_true", help="re-decode everything")
    b.set_defaults(func=cmd_baseline)

    sub.add_parser("verify").set_defaults(func=cmd_verify)
    sub.add_parser("stats").set_defaults(func=cmd_stats)

    du = sub.add_parser("dump")
    du.add_argument("path")
    du.add_argument("-o", "--out")
    du.set_defaults(func=cmd_dump)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
