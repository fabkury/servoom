"""Check the 0x1D layer-file decoder against the flattened artworks of this archive.

For every ``<id>_layer.dat`` whose first byte is 0x1D, decode it with servoom, composite
each frame and compare with the frames of the matching ``<id>.dat`` artwork (decoded
losslessly by ``PixelBeanDecoder``; the WebP next to it merges identical frames, so it is
not the reference). Two renderings are tried, because the app's HSL math changed in
June 2023 (see python/layer-tools/LAYER_FILE_FORMAT.md, section 4):

* ``integer`` -- the 3.8.40 pipeline (h, s, l quantised), also used by the 0x27/0x28 era;
* ``float``   -- the unquantised pipeline of the app that wrote files from 2023-06-20 on.

Run from python/:  python ../requests/04-thepixelxb/validate_0x1d.py [--csv out.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "python"))
from servoom.layer_file_decoder import LayerFileDecoder  # noqa: E402
from servoom.pixel_bean_decoder import PixelBeanDecoder  # noqa: E402

ARTWORKS = HERE / "package" / "artworks"
FLOAT_ERA_FROM = "2023-06-20"  # first upload date rendered with the float HSL pipeline


def compare(layer, frames, mode):
    """Return (bad_frames, bad_pixels, max_abs_diff) of the composite against the artwork."""
    bad_f = bad_px = maxd = 0
    for i, ref in enumerate(frames):
        comp = layer.composite_frame(i, hsl_mode=mode)
        if comp.shape != ref.shape:
            return len(frames), ref.size // 3 * len(frames), 255
        diff = np.abs(comp.astype(int) - ref.astype(int))
        n = int(np.any(diff > 0, axis=2).sum())
        if n:
            bad_f += 1
            bad_px += n
            maxd = max(maxd, int(diff.max()))
    return bad_f, bad_px, maxd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, help="write one row per file")
    args = ap.parse_args()

    rows = []
    for d in sorted(ARTWORKS.iterdir()):
        meta_path = d / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        files = meta.get("files", {})
        if "layer" not in files or "artwork" not in files:
            continue
        lpath = d / files["layer"]
        if lpath.read_bytes()[:1] != b"\x1d":
            continue
        gid = meta["gallery"]["GalleryId"]
        day = d.name[:10]
        row = {"gallery_id": gid, "date": day, "dir": d.name}
        try:
            layer = LayerFileDecoder.decode_file(str(lpath))
        except Exception as exc:  # noqa: BLE001 - report, do not stop
            row.update(status="decode-error", error=str(exc))
            rows.append(row)
            continue
        bean = PixelBeanDecoder.decode_file(str(d / files["artwork"]))
        fmt = (d / files["artwork"]).read_bytes()[0]
        hsl_layers = sum(1 for fm in layer.frames_meta for l in fm["layers"]
                         if l["hue"] or l["saturation"] or l["lightness"])
        row.update(side=layer.width, frames=layer.num_frames, layers=layer.total_layers,
                   hsl_layers=hsl_layers, artwork_format=fmt, artwork_side=bean.width,
                   artwork_frames=bean.total_frames)
        if bean.width != layer.width:
            row.update(status="size-mismatch")  # the artwork is not a render of this file
            rows.append(row)
            continue
        if bean.total_frames != layer.num_frames:
            row.update(status="frame-count-mismatch")
            rows.append(row)
            continue
        for mode in ("integer", "float"):
            bf, bp, md = compare(layer, bean.frames_data, mode)
            row.update({f"{mode}_bad_frames": bf, f"{mode}_bad_pixels": bp, f"{mode}_maxdiff": md})
        era_mode = "float" if day >= FLOAT_ERA_FROM else "integer"
        row["era_mode"] = era_mode
        if row["integer_bad_frames"] == 0 or row["float_bad_frames"] == 0:
            row["status"] = "exact"
        elif fmt == 31:
            row["status"] = "lossy-artwork"  # format 31 is JPEG-coded: never byte-exact
        elif hsl_layers and row[f"{era_mode}_maxdiff"] <= 8:
            row["status"] = "hsl-rounding"   # +-1..8 on HSL layers only: float residue
        else:
            row["status"] = "content-differs"  # artwork re-rendered after the layer file
        rows.append(row)

    total = len(rows)
    by = Counter(r["status"] for r in rows)
    exact_int = sum(1 for r in rows if r.get("integer_bad_frames") == 0)
    exact_float = sum(1 for r in rows if r.get("float_bad_frames") == 0)
    exact_era = sum(1 for r in rows if r.get(f"{r.get('era_mode')}_bad_frames") == 0)
    decoded = sum(1 for r in rows if r["status"] != "decode-error")
    print(f"0x1D layer files: {total}")
    print(f"  decoded:                       {decoded}")
    print(f"  composite == artwork, integer HSL: {exact_int}")
    print(f"  composite == artwork, float HSL:   {exact_float}")
    print(f"  composite == artwork, HSL by date: {exact_era}")
    print(f"  composite == artwork, either:      {by['exact']}")
    for k in ("hsl-rounding", "content-differs", "lossy-artwork", "size-mismatch",
              "frame-count-mismatch", "decode-error"):
        if by[k]:
            print(f"  {k + ':':31s}{by[k]}")
    sizes = Counter((r.get("side"), r["status"] == "exact") for r in rows)
    for side in (16, 32, 64, 128):
        n = sum(v for (s, _), v in sizes.items() if s == side)
        e = sizes[(side, True)]
        print(f"  {side}x{side}: {e}/{n} exact")
    if args.csv:
        keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("gallery_id", "date", "status"), k))
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.csv}")


if __name__ == "__main__":
    main()
