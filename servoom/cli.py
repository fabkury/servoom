"""Command-line interface: ``python -m servoom <command>``.

Commands:
  decode        decode a pixel .dat (or a folder of them) to WebP/GIF
  decode-layer  decode a 0x27 layer file to WebP and/or layered PSD
  download      download + decode one artwork by gallery id (needs credentials)
  download-user download every artwork of a user      (needs credentials)

Credentials (for the download commands) come from the environment
(``SERVOOM_EMAIL`` / ``SERVOOM_MD5_PASSWORD``) or a ``credentials.py`` — see
:mod:`servoom.credentials`.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .layer_file_decoder import LayerFileDecoder
from .logging import configure, get_logger
from .pixel_bean_decoder import PixelBeanDecoder

log = get_logger(__name__)


def _decode_one(path: Path, out_dir: Path, fmt: str) -> bool:
    bean = PixelBeanDecoder.decode_file(str(path))
    if bean is None:
        log.warning("[SKIP] unsupported/failed: %s", path.name)
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem.split("_")[0] or path.stem
    out = out_dir / f"{stem}.{fmt}"
    if fmt == "gif":
        bean.save_to_gif(str(out))
    else:
        bean.save_to_webp(str(out))
    log.info("[OK] %s -> %s (%d frames, %dx%d)",
             path.name, out.name, bean.total_frames, bean.width, bean.height)
    return True


def _cmd_decode(args) -> int:
    src = Path(args.path)
    out_dir = Path(args.out)
    paths = sorted(src.glob("*.dat")) if src.is_dir() else [src]
    if not paths:
        log.error("No .dat files at %s", src)
        return 1
    ok = sum(_decode_one(p, out_dir, args.format) for p in paths)
    log.info("Decoded %d/%d", ok, len(paths))
    return 0 if ok else 1


def _cmd_decode_layer(args) -> int:
    layer = LayerFileDecoder.decode_file(args.path)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.path).stem or "layer"
    layer.save_to_webp(str(out_dir / f"{stem}.webp"))
    log.info("[OK] %s -> %s.webp (%d frames, %d layers)",
             Path(args.path).name, stem, layer.num_frames, layer.total_layers)
    if args.psd:
        layer.save_to_psd(str(out_dir / f"{stem}.psd"))
        log.info("[OK] wrote %s.psd", stem)
    return 0


def _client(args):
    from .client import DivoomClient  # imported lazily so decode works without requests

    client = DivoomClient(email=args.email, md5_password=args.md5_password)
    if not client.login():
        raise SystemExit("Login failed")
    return client


def _cmd_download(args) -> int:
    client = _client(args)
    bean, path = client.download_art_by_id(args.gallery_id, output_dir=args.out)
    client.decode_art(bean)
    out = os.path.join(args.out, os.path.splitext(os.path.basename(path))[0] + ".webp")
    bean.save_to_webp(out)
    log.info("[OK] %s -> %s", args.gallery_id, out)
    return 0


def _cmd_download_user(args) -> int:
    client = _client(args)
    paths = client.download_someone_arts(args.user_id, output_dir=args.out, limit=args.limit)
    log.info("Downloaded %d files", len(paths))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="servoom", description=__doc__.splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("decode", help="decode a pixel .dat (or folder) to WebP/GIF")
    d.add_argument("path")
    d.add_argument("-o", "--out", default="out")
    d.add_argument("-f", "--format", choices=["webp", "gif"], default="webp")
    d.set_defaults(func=_cmd_decode)

    dl = sub.add_parser("decode-layer", help="decode a 0x27 layer file to WebP/PSD")
    dl.add_argument("path")
    dl.add_argument("-o", "--out", default="out")
    dl.add_argument("--psd", action="store_true", help="also write a layered PSD")
    dl.set_defaults(func=_cmd_decode_layer)

    for name, help_text, extra in (
        ("download", "download + decode one artwork by gallery id",
         [("gallery_id", int)]),
        ("download-user", "download every artwork of a user", [("user_id", int)]),
    ):
        p = sub.add_parser(name, help=help_text)
        for arg, typ in extra:
            p.add_argument(arg, type=typ)
        p.add_argument("-o", "--out", default="downloads")
        p.add_argument("--email", default=None)
        p.add_argument("--md5-password", dest="md5_password", default=None)
        if name == "download-user":
            p.add_argument("--limit", type=int, default=None)
    parser.set_defaults(func=None)
    sub.choices["download"].set_defaults(func=_cmd_download)
    sub.choices["download-user"].set_defaults(func=_cmd_download_user)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    configure()
    if args.verbose:
        import logging
        configure(logging.DEBUG)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
