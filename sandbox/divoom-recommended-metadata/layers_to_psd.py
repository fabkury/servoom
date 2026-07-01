"""
Convert Divoom layer file(s) (container format 0x27) into layered PSD files that GIMP or
Photoshop can open with layers intact.

Thin CLI over servoom.LayerFileDecoder + LayerBean.save_to_psd(): each animation frame
becomes a layer group; inside it, one PSD layer per Divoom layer. Per-layer opacity and
the hidden flag are preserved, black is treated as transparent, and stacking is
bottom -> top (frame 0 and layer 0 at the bottom), matching the Divoom paint order.

Requires ``pytoshop`` in addition to the servoom dependencies:
    pip install pytoshop

Usage:
    # a single layer file
    python layers_to_psd.py path/to/layer.dat [-o OUT_DIR]

    # a directory of pair-*/layer.dat (as produced during the layer-format work)
    python layers_to_psd.py path/to/pairs_dir --batch [-o OUT_DIR]
"""

import argparse
import glob
import os
import sys

# Allow running straight from the repo without installing the package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from servoom import LayerFileDecoder  # noqa: E402


def convert(layer_path: str, out_path: str, all_frames_visible: bool = True):
    """Decode one layer file and write a layered PSD; return (LayerBean, bytes_written)."""
    layer = LayerFileDecoder.decode_file(layer_path)
    layer.save_to_psd(out_path, all_frames_visible=all_frames_visible)
    return layer, os.path.getsize(out_path)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Divoom layer files (format 0x27) to layered PSD.",
    )
    parser.add_argument("path", help="a layer .dat file, or a directory when --batch is set")
    parser.add_argument("-o", "--out", default="gimp_psd", help="output directory (default: gimp_psd)")
    parser.add_argument(
        "--batch", action="store_true",
        help="treat PATH as a directory containing pair-*/layer.dat",
    )
    parser.add_argument(
        "--first-frame-only-visible", action="store_true",
        help="show only frame 0's group by default (default: all frame groups visible)",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    os.makedirs(args.out, exist_ok=True)
    all_frames_visible = not args.first_frame_only_visible

    if args.batch:
        pairs = sorted(glob.glob(os.path.join(args.path, "pair-*")))
        print(f"Converting {len(pairs)} layer files -> {args.out}/\n")
        ok = 0
        for d in pairs:
            name = os.path.basename(d)
            out = os.path.join(args.out, f"{name}.psd")
            try:
                layer, size = convert(os.path.join(d, "layer.dat"), out, all_frames_visible)
                print(f"[OK]   {name}: {layer.width}x{layer.height} {layer.num_frames} frames, "
                      f"{layer.total_layers} layers -> {os.path.basename(out)} ({size // 1024} KB)")
                ok += 1
            except Exception as exc:
                print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
        print(f"\nWrote {ok}/{len(pairs)} PSDs to {args.out}/")
    else:
        base = os.path.splitext(os.path.basename(args.path))[0] or "layer"
        out = os.path.join(args.out, f"{base}.psd")
        layer, size = convert(args.path, out, all_frames_visible)
        print(f"[OK] {layer.width}x{layer.height} {layer.num_frames} frames, "
              f"{layer.total_layers} layers -> {out} ({size // 1024} KB)")


if __name__ == "__main__":
    main()
