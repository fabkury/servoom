"""
Divoom LAYER file decoder  (file format 0x27 / 39)  -- reverse-engineered.

A Divoom "layer file" (LayerFileId) is the editable, layered source for an artwork.
This decoder is fully self-contained: it needs ONLY the layer .dat file. It parses the
container, recovers every layer bitmap (raw 24-bit RGB), the per-frame layer structure,
and per-layer opacity, and can composite the layers back into the animation.

------------------------------------------------------------------------------------
CONTAINER LAYOUT  (all multi-byte integers are big-endian)
------------------------------------------------------------------------------------
  offset 0 : uint8   format id = 0x27 (39)  or  0x28 (40)
  STREAM 0 ("layer table"), both formats: a length-prefixed zstd stream
        uint32 C   = compressed size of the stream
        uint32 U   = uncompressed size of the stream
        bytes[C]   = a single zstd frame (magic 28 B5 2F FD) -> U bytes
  PIXELS follow, encoded per format id:
    0x27: STREAM 1 = a second zstd stream of K raw 24-bit RGB bitmaps, back to back.
    0x28: K records, each [uint8 flag][uint32 BE length][lossless WEBP image] (one per layer).

STREAM 0  (layer table), repeated for each animation frame until exhausted:
    uint8  num_layers          number of layers in this frame
    uint8  active/flag          (unconfirmed; likely the editor's selected-layer index)
    num_layers x 6-byte layer descriptor:
        byte[0]                 HIDDEN   nonzero => layer hidden (skipped)  <-- confirmed
        byte[1]                 OPACITY  0..255   <-- confirmed
        byte[2]                 (varies; unknown)
        byte[3:6]               near-constant (b4 64 64 typical); unknown/reserved
  The number of frame records equals the artwork's declared frame count, and the sum of
  num_layers over all frames equals K (the number of bitmaps in stream 1).

PIXELS:
    K bitmaps ordered frame-major: all layers of frame 0 (bottom->top), then frame 1, ...
    0x27: each bitmap is  width*height*3  bytes, row-major RGB, 8 bits/channel, stored
          back-to-back in STREAM 1. Canvas is square, so side = sqrt(len(stream1)/(3*K)).
    0x28: each bitmap is a lossless WEBP image (RGB); side comes from the WEBP dimensions.

COMPOSITING (matches the Divoom editor):
    * The colour BLACK (0,0,0) is TRANSPARENT.
    * Layers are painted bottom -> top over a black canvas.
    * Each layer is alpha-blended with alpha = opacity/255:
          canvas[p] = layer[p]*alpha + canvas[p]*(1-alpha)   for non-black p
  This reproduces the decoded artwork frames to within the artwork decoder's own
  quantization (~+-4) on the validation sample; single-layer frames match exactly.

Unknowns still open: exact meaning of descriptor bytes [0],[2],[3:6]; the record flag
byte; whether frame duration is stored (it is 0 in the header here -- speed lives in the
artwork file, not the layer file).

Usage:
    python divoom_layer_decoder.py <layer.dat> [--out DIR] [--layers] [--duration MS]
    python divoom_layer_decoder.py --batch layer_artwork_pairs --out layer_decoded
"""

import argparse
import io
import math
import os
import sys
from struct import unpack

import numpy as np
import zstandard as zstd
from PIL import Image

FORMAT_RAW_RGB = 0x27   # pixels = one zstd stream of raw 24-bit RGB bitmaps
FORMAT_WEBP = 0x28      # pixels = per-layer [uint8 flag][uint32 BE length][lossless WEBP]
SUPPORTED_FORMATS = (FORMAT_RAW_RGB, FORMAT_WEBP)
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _read_zstd_stream(data: bytes, pos: int):
    """Read one length-prefixed zstd stream at pos; return (decompressed_bytes, next_pos)."""
    c = unpack(">I", data[pos : pos + 4])[0]
    u = unpack(">I", data[pos + 4 : pos + 8])[0]
    comp = data[pos + 8 : pos + 8 + c]
    if comp[:4] != ZSTD_MAGIC:
        raise ValueError(f"expected zstd magic at offset {pos+8}")
    dec = zstd.ZstdDecompressor().decompressobj().decompress(comp)
    if len(dec) != u:
        raise ValueError(f"stream size mismatch: header says {u}, got {len(dec)}")
    return dec, pos + 8 + c


def _parse_layer_table(stream0: bytes):
    """Parse the per-frame layer table. Returns list of frames; each frame is a dict."""
    pos = 0
    frames = []
    while pos + 2 <= len(stream0):
        num_layers = stream0[pos]
        flag = stream0[pos + 1]
        pos += 2
        layers = []
        for _ in range(num_layers):
            desc = stream0[pos : pos + 6]
            pos += 6
            layers.append({"hidden": desc[0] != 0, "opacity": desc[1], "descriptor": desc.hex()})
        frames.append({"num_layers": num_layers, "flag": flag, "layers": layers})
    if pos != len(stream0):
        raise ValueError(f"layer table did not consume stream0 exactly ({pos} != {len(stream0)})")
    return frames


class DivoomLayerFile:
    def __init__(self, data: bytes):
        if not data or data[0] not in SUPPORTED_FORMATS:
            got = f"0x{data[0]:02x}" if data else None
            raise ValueError(f"not a 0x27/0x28 layer file (first byte = {got})")
        self.format = data[0]

        # Stream 0 (layer table) is a zstd stream in both formats.
        self.stream0, pos = _read_zstd_stream(data, 1)
        self.frames_meta = _parse_layer_table(self.stream0)
        self.total_layers = sum(f["num_layers"] for f in self.frames_meta)

        if self.format == FORMAT_RAW_RGB:
            stream1, _ = _read_zstd_stream(data, pos)
            px = len(stream1)
            side_sq = px / (3 * self.total_layers) if self.total_layers else 0
            side = int(round(math.sqrt(side_sq)))
            if side * side != int(round(side_sq)) or side * side * 3 * self.total_layers != px:
                raise ValueError(f"pixel stream {px} not K*side^2*3 (K={self.total_layers})")
            self.width = self.height = side
            self.bitmaps = np.frombuffer(stream1, np.uint8).reshape(
                self.total_layers, side, side, 3
            )
        else:  # FORMAT_WEBP: K records of [uint8 flag][uint32 BE length][lossless WEBP]
            layers = []
            side = None
            for i in range(self.total_layers):
                length = unpack(">I", data[pos + 1 : pos + 5])[0]  # data[pos] = reserved flag
                webp = data[pos + 5 : pos + 5 + length]
                pos += 5 + length
                arr = np.array(Image.open(io.BytesIO(webp)).convert("RGB"), np.uint8)
                if side is None:
                    side = arr.shape[0]
                if arr.shape != (side, side, 3):
                    raise ValueError(f"layer {i}: expected {side}x{side} RGB, got {arr.shape}")
                layers.append(arr)
            self.width = self.height = side
            self.bitmaps = np.stack(layers)

        # Split into per-frame layer stacks (bottom -> top).
        self.frames = []
        idx = 0
        for fm in self.frames_meta:
            n = fm["num_layers"]
            self.frames.append(self.bitmaps[idx : idx + n])
            idx += n

    @property
    def num_frames(self):
        return len(self.frames_meta)

    def composite_frame(self, f: int) -> np.ndarray:
        """Alpha-composite frame f (black = transparent, bottom -> top). Skips hidden layers."""
        layers = self.frames[f]
        metas = self.frames_meta[f]["layers"]
        canvas = np.zeros((self.height, self.width, 3), dtype=float)
        for L, meta in zip(layers, metas):
            if meta.get("hidden"):
                continue
            a = meta["opacity"] / 255.0
            mask = np.any(L != 0, axis=2)
            canvas[mask] = L[mask].astype(float) * a + canvas[mask] * (1.0 - a)
        return np.clip(np.round(canvas), 0, 255).astype(np.uint8)

    def report(self) -> str:
        pixel_kind = "raw RGB (zstd)" if self.format == FORMAT_RAW_RGB else "lossless WEBP"
        lines = [
            f"format            : 0x{self.format:02x} ({self.format})  Divoom layer file",
            f"canvas            : {self.width}x{self.height}",
            f"frames            : {self.num_frames}",
            f"total layers (K)  : {self.total_layers}",
            f"pixel encoding    : {pixel_kind}",
            f"layers per frame  : {[f['num_layers'] for f in self.frames_meta]}",
        ]
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def save_composite_webp(lf: DivoomLayerFile, path: str, duration_ms: int = 100):
    imgs = [Image.fromarray(lf.composite_frame(f), "RGB") for f in range(lf.num_frames)]
    imgs[0].save(path, append_images=imgs[1:], duration=duration_ms,
                 save_all=True, loop=0, disposal=0, lossless=True)


def save_layer_pngs(lf: DivoomLayerFile, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    for f in range(lf.num_frames):
        for l in range(lf.frames_meta[f]["num_layers"]):
            op = lf.frames_meta[f]["layers"][l]["opacity"]
            img = Image.fromarray(lf.frames[f][l], "RGB")
            img.save(os.path.join(out_dir, f"frame{f:03d}_layer{l:02d}_op{op:03d}.png"))


def decode_one(layer_path: str, out_dir: str, dump_layers: bool, duration: int):
    with open(layer_path, "rb") as fh:
        lf = DivoomLayerFile(fh.read())
    os.makedirs(out_dir, exist_ok=True)
    print(lf.report())
    webp = os.path.join(out_dir, "composited.webp")
    save_composite_webp(lf, webp, duration)
    print(f"  -> {webp}")
    if dump_layers:
        ldir = os.path.join(out_dir, "layers")
        save_layer_pngs(lf, ldir)
        print(f"  -> {ldir}/ ({lf.total_layers} layer PNGs)")
    return lf


def main():
    ap = argparse.ArgumentParser(description="Decode Divoom 0x27 layer files.")
    ap.add_argument("path", help="layer.dat file, or a pairs dir when --batch is set")
    ap.add_argument("--out", default="layer_decoded", help="output directory")
    ap.add_argument("--layers", action="store_true", help="also dump per-layer PNGs")
    ap.add_argument("--duration", type=int, default=100, help="webp frame duration ms")
    ap.add_argument("--batch", action="store_true",
                    help="treat path as a dir of pair-*/layer.dat")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.batch:
        import glob
        pairs = sorted(glob.glob(os.path.join(args.path, "pair-*")))
        print(f"Decoding {len(pairs)} layer files...\n")
        ok = 0
        for d in pairs:
            lp = os.path.join(d, "layer.dat")
            name = os.path.basename(d)
            try:
                print(f"=== {name} ===")
                decode_one(lp, os.path.join(args.out, name), args.layers, args.duration)
                ok += 1
            except Exception as exc:
                print(f"  [FAIL] {type(exc).__name__}: {exc}")
            print()
        print(f"Decoded {ok}/{len(pairs)} layer files -> {args.out}/")
    else:
        decode_one(args.path, args.out, args.layers, args.duration)


if __name__ == "__main__":
    main()
