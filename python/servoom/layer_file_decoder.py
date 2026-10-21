"""
Decoder for Divoom LAYER files (container format 0x27 / 39).

A Divoom layer file (referenced by ``LayerFileId`` in gallery metadata) is the editable,
layered source for an artwork; the artwork file (``FileId``) is the flattened render.
This module recovers every layer bitmap, the per-frame layer structure and per-layer
opacity, and can re-composite the animation the way the Divoom editor does.

Two container versions are supported. Both start with a **layer table** (a length-prefixed
zstd stream) and differ only in how the layer bitmaps are stored (big-endian integers)::

    offset 0 : uint8   format id = 0x27 (39)  or  0x28 (40)
    stream 0 (both):   uint32 C | uint32 U | bytes[C]  -- one zstd frame -> U bytes
                       = the LAYER TABLE

* **layer table**: for each animation frame ``uint8 num_layers``, ``uint8 active_layer``
  (the editor's last selected layer index), then ``num_layers`` x 6-byte descriptors:
  ``byte[0]`` HIDDEN flag (nonzero => layer hidden, excluded from the composite),
  ``byte[1]`` OPACITY (0-255), ``uint16 BE [2:4]`` = hue + 180 (-180..180),
  ``byte[4]`` = saturation + 100 and ``byte[5]`` = lightness + 100 (-100..100) -- the
  editor's per-layer HSL slider positions. ``K`` = sum of ``num_layers``.

* **pixels, format 0x27**: a *second* length-prefixed zstd stream holding ``K`` layer
  bitmaps, each ``side*side*3`` bytes of raw 24-bit RGB, frame-major (bottom -> top). The
  canvas is square, so ``side = sqrt(len(stream1) / (3*K))``.
* **pixels, format 0x28**: ``K`` records, each ``uint8 flag`` (reserved; observed 0),
  ``uint32 BE length``, then a lossless **WEBP** image of the layer bitmap (RGB, black =
  transparent, same as 0x27). ``side`` comes from the WEBP dimensions.

Compositing (matches the app): the colour black ``(0,0,0)`` is transparent; layers are
painted bottom -> top over a black canvas, a layer's HSL sliders are applied to its painted
pixels first (:func:`adjust_hsl`), then each is alpha-blended with ``opacity/255`` in single
precision and truncated, like the Android editor.

See ``layer-tools/LAYER_FILE_FORMAT.md`` for the full reverse-engineering write-up.
"""

import io
import math
from io import IOBase
from struct import unpack
from typing import Dict, List, Optional, Tuple

import numpy as np
import zstandard as zstd
from PIL import Image

from .pixel_bean import PixelBean

# Layer-file container format ids. Both share the same zstd layer-table stream; they differ
# only in how the layer bitmaps are stored (see the two _bitmaps_from_* helpers):
FORMAT_RAW_RGB = 0x27   # pixels = one zstd stream of K raw 24-bit RGB bitmaps
FORMAT_WEBP = 0x28      # pixels = K records of [uint8 flag][uint32 BE length][lossless WEBP]
SUPPORTED_FORMATS = (FORMAT_RAW_RGB, FORMAT_WEBP)
FORMAT_ID = FORMAT_RAW_RGB  # backwards-compatible alias
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
DESCRIPTOR_SIZE = 6


def adjust_hsl(rgb: np.ndarray, hue: int, saturation: int, lightness: int) -> np.ndarray:
    """Apply a layer's Hue/Saturation/Lightness sliders to an ``(..., 3)`` uint8 bitmap.

    Reproduces the editor's integer HSL pipeline so composites match the app's render:

    * RGB -> HSL in single precision, quantised to ``h`` 0..359, ``s`` 0..100, ``l`` 0..100
      by truncation;
    * ``h += hue`` (wrapped into 0..359); a negative ``saturation`` / ``lightness`` scales
      ``s`` / ``l`` by ``1 + v/100`` (truncated), a positive one is added; ``s`` is only
      changed when it was non-zero; both are clamped to 0..100;
    * HSL -> RGB in single precision, each channel truncated to 0..255.

    Black pixels are transparent and never adjusted; the caller masks them. A pixel can
    *become* black (lightness -100) and is then treated as transparent by the blend.
    """
    f32 = np.float32
    shape = rgb.shape
    px = rgb.reshape(-1, 3).astype(f32) / f32(255.0)
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    summ = mx + mn
    l_f = summ / f32(2.0)
    d = mx - mn
    chroma = d != 0
    denom = np.where(l_f.astype(np.float64) > 0.5, (f32(2.0) - mx) - mn, summ).astype(f32)
    with np.errstate(divide="ignore", invalid="ignore"):
        s_f = np.where(chroma, d / denom, f32(0.0)).astype(f32)
        h_r = (g - b) / d + np.where(g < b, f32(6.0), f32(0.0))
        h_g = (b - r) / d + f32(2.0)
        h_b = (r - g) / d + f32(4.0)
    h_f = np.where(mx == r, h_r, np.where(mx == g, h_g, h_b)).astype(f32) / f32(6.0)
    h_f = np.where(chroma, h_f, f32(0.0)).astype(f32)
    h = np.trunc(h_f * f32(360.0)).astype(np.int32)
    s = np.trunc(s_f * f32(100.0)).astype(np.int32)
    lv = np.trunc(l_f * f32(100.0)).astype(np.int32)

    if hue:
        h = h + hue
        h = np.where(h >= 360, h - 360, h)
        h = np.where(h < 0, h + 360, h)
    if saturation < 0:
        s = np.where(s != 0, np.trunc(s + s * (saturation / 100.0)).astype(np.int32), s)
    elif saturation > 0:
        s = np.where(s != 0, s + saturation, s)
    if lightness < 0:
        lv = np.trunc(lv + lv * (lightness / 100.0)).astype(np.int32)
    elif lightness > 0:
        lv = lv + lightness
    s = np.clip(s, 0, 100)
    lv = np.clip(lv, 0, 100)

    hf = (h / 360.0).astype(f32)
    sf = (s / 100.0).astype(f32)
    lf = (lv / 100.0).astype(f32)
    q = np.where(lf.astype(np.float64) < 0.5, (sf + f32(1.0)) * lf, (lf + sf) - sf * lf).astype(f32)
    p = lf * f32(2.0) - q

    def hue_to_channel(t: np.ndarray) -> np.ndarray:
        t = t.astype(f32)
        t = np.where(t < 0, t + f32(1.0), t).astype(f32)
        t = np.where(t > 1, t - f32(1.0), t).astype(f32)
        td = t.astype(np.float64)
        seg1 = p + (q - p) * f32(6.0) * t
        seg3 = (p.astype(np.float64) + (q - p).astype(np.float64) * (2.0 / 3.0 - td) * 6.0).astype(f32)
        return np.where(td < 1.0 / 6.0, seg1,
                        np.where(td < 0.5, q, np.where(td < 2.0 / 3.0, seg3, p))).astype(f32)

    hd = hf.astype(np.float64)
    r_out = hue_to_channel((hd + 1.0 / 3.0).astype(f32))
    g_out = hue_to_channel(hf)
    b_out = hue_to_channel((hd - 1.0 / 3.0).astype(f32))
    gray = np.trunc(lf * f32(255.0))
    out = np.stack([
        np.where(sf == 0, gray, np.trunc(r_out * f32(255.0))),
        np.where(sf == 0, gray, np.trunc(g_out * f32(255.0))),
        np.where(sf == 0, gray, np.trunc(b_out * f32(255.0))),
    ], axis=1)
    return np.clip(out, 0, 255).astype(np.uint8).reshape(shape)


def hsl_name_tag(meta: Dict) -> str:
    """PSD layer-name suffix for a layer's HSL sliders: ``_hue-30_sat10_lit0`` (all three,
    only when at least one is non-neutral) or ``""`` when all are 0."""
    hue, sat, lit = meta.get("hue", 0), meta.get("saturation", 0), meta.get("lightness", 0)
    if hue == 0 and sat == 0 and lit == 0:
        return ""
    return f"_hue{hue}_sat{sat}_lit{lit}"


class LayerBean(object):
    """Decoded Divoom layer file: layer bitmaps, per-frame structure and opacities."""

    def __init__(
        self,
        width: int,
        height: int,
        frames_meta: List[Dict],
        frame_layers: List[np.ndarray],
        streams_meta: Optional[List] = None,
    ):
        self._width = width
        self._height = height
        self._frames_meta = frames_meta
        self._frame_layers = frame_layers  # list (per frame) of (n, H, W, 3) uint8 arrays
        self._streams_meta = streams_meta or []

    # -- basic properties ---------------------------------------------------
    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def row_count(self) -> int:
        return self._height // 16

    @property
    def column_count(self) -> int:
        return self._width // 16

    @property
    def num_frames(self) -> int:
        return len(self._frames_meta)

    @property
    def total_layers(self) -> int:
        return sum(f["num_layers"] for f in self._frames_meta)

    @property
    def frames_meta(self) -> List[Dict]:
        """Per-frame metadata: ``num_layers``, ``flag`` and per-layer ``opacity``/``descriptor``."""
        return self._frames_meta

    def frame_layers(self, frame: int) -> np.ndarray:
        """Raw layer bitmaps for ``frame`` as an ``(n, H, W, 3)`` uint8 array (bottom -> top)."""
        return self._frame_layers[frame]

    # -- compositing --------------------------------------------------------
    def composite_frame(self, frame: int) -> np.ndarray:
        """Composite ``frame`` the way the Divoom editor renders it, to ``(H, W, 3)``.

        Bottom -> top: hidden layers are skipped; a layer whose HSL sliders are not all
        zero has every painted (non-black) pixel adjusted first (:func:`adjust_hsl`); then
        each painted pixel is blended over the canvas with ``alpha = opacity/255`` in
        single-precision arithmetic and truncated to an integer, like the app. Black
        ``(0,0,0)`` -- also a pixel that *became* black through the sliders -- is
        transparent and leaves the canvas untouched.
        """
        layers = self._frame_layers[frame]
        metas = self._frames_meta[frame]["layers"]
        canvas = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        for layer, meta in zip(layers, metas):
            if meta["hidden"]:
                continue
            mask = np.any(layer != 0, axis=2)  # non-black SOURCE pixels are painted
            if not mask.any():
                continue
            painted = layer[mask]
            if meta.get("hue", 0) or meta.get("saturation", 0) or meta.get("lightness", 0):
                # Only painted pixels go through the sliders (a transparent pixel must not
                # turn into a lit one); a pixel that comes out black is transparent too.
                painted = adjust_hsl(painted, meta["hue"], meta["saturation"], meta["lightness"])
                still = np.any(painted != 0, axis=1)
                idx = np.flatnonzero(mask.ravel())[still]
                mask = np.zeros(mask.shape, dtype=bool)
                mask.ravel()[idx] = True
                painted = painted[still]
                if not len(painted):
                    continue
            alpha = np.float32(meta["opacity"] / 255.0)
            src = painted.astype(np.float32) * alpha
            dst = canvas[mask].astype(np.float32) * (np.float32(1.0) - alpha)
            canvas[mask] = np.trunc(src + dst).astype(np.uint8)
        return canvas

    def to_pixel_bean(self, metadata: Optional[Dict] = None, speed: int = 100) -> PixelBean:
        """Composite all frames into a ``PixelBean`` (COMPLETE) reusing its export helpers."""
        frames_data = [self.composite_frame(f) for f in range(self.num_frames)]
        return PixelBean(
            metadata=metadata or {},
            total_frames=self.num_frames,
            speed=speed,
            row_count=self.row_count,
            column_count=self.column_count,
            frames_data=frames_data,
        )

    def save_to_webp(self, output_path: str, speed: int = 100, **kwargs) -> None:
        """Composite and save an animated lossless WebP (delegates to ``PixelBean``)."""
        self.to_pixel_bean(speed=speed).save_to_webp(output_path, **kwargs)

    def save_to_psd(
        self,
        output_path: str,
        all_frames_visible: bool = True,
        compression: str = "zip",
    ) -> None:
        """Export to a layered PSD that GIMP (and Photoshop) can open with layers intact.

        Each animation frame becomes a layer *group* (``frameNNN``); inside it, one PSD
        layer per Divoom layer. Preserved:

        * per-layer **opacity** (descriptor byte[1]),
        * the **hidden** flag (descriptor byte[0]) -> PSD layer visibility,
        * **black = transparent** -> each layer gets an alpha channel (0 where black).

        Because black is the chroma key, every frame group also gets an opaque black
        background layer (``fNNN_bg``) at its bottom, so pixels that are transparent in
        all of a frame's layers render black -- exactly as the Divoom app composites them.

        Stacking is bottom -> top: frame 0 is the bottom-most group and, within each
        frame, the black background is the bottom-most layer followed by layer 0 --
        matching the Divoom paint order.

        Args:
            output_path: destination ``.psd`` path.
            all_frames_visible: if True (default) every frame group is visible; if False
                only the first frame's group is visible (handy for editing one frame).
            compression: PSD channel compression -- ``"zip"`` (default), ``"raw"`` or
                ``"rle"``. ``"zip"`` is recommended.

        Requires the optional ``pytoshop`` package (``pip install pytoshop``).
        """
        try:
            from pytoshop.user import nested_layers
            from pytoshop import enums
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "PSD export requires the 'pytoshop' package. Install it with "
                "'pip install pytoshop'."
            ) from exc

        comp_map = {
            "zip": enums.Compression.zip,
            "raw": enums.Compression.raw,
            "rle": enums.Compression.rle,
        }
        if compression not in comp_map:
            raise ValueError(f"compression must be one of {sorted(comp_map)}")

        def _image_layer(name, rgb, opacity, visible, alpha=None):
            # Divoom treats black (0,0,0) as transparent -> derive an alpha channel.
            if alpha is None:
                alpha = (np.any(rgb != 0, axis=2).astype(np.uint8)) * 255
            if not alpha.any():
                # pytoshop silently DROPS a layer whose alpha is all zero, which would lose
                # an empty Divoom layer (and shift layer indices). Write it as a 0x0 layer
                # with constant channels instead: still listed, still transparent.
                return nested_layers.Image(
                    name=name, visible=visible, opacity=opacity,
                    top=0, left=0, bottom=0, right=0,
                    channels={0: 0, 1: 0, 2: 0, -1: 255}, color_mode=enums.ColorMode.rgb,
                )
            channels = {
                0: np.ascontiguousarray(rgb[:, :, 0]),
                1: np.ascontiguousarray(rgb[:, :, 1]),
                2: np.ascontiguousarray(rgb[:, :, 2]),
                -1: alpha,  # transparency channel
            }
            return nested_layers.Image(
                name=name, visible=visible, opacity=opacity,
                top=0, left=0, bottom=self._height, right=self._width,
                channels=channels, color_mode=enums.ColorMode.rgb,
            )

        # pytoshop/PSD order: the FIRST list element is the TOP of the stack, so reverse
        # both levels to place frame 0 / layer 0 at the bottom.
        black = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        opaque = np.full((self._height, self._width), 255, dtype=np.uint8)

        groups = []
        for f in range(self.num_frames):
            # Black is the chroma key: an opaque black background under each frame's
            # layers makes fully-transparent pixels render black, like the Divoom app.
            items = [_image_layer(f"f{f:03d}_bg", black, 255, True, alpha=opaque)]
            for li, meta in enumerate(self._frames_meta[f]["layers"]):
                rgb = self._frame_layers[f][li]
                name = f"f{f:03d}_l{li:02d}_op{meta['opacity']:03d}{hsl_name_tag(meta)}"
                name += "_HIDDEN" if meta["hidden"] else ""
                items.append(_image_layer(name, rgb, meta["opacity"], not meta["hidden"]))
            group_visible = True if all_frames_visible else (f == 0)
            groups.append(nested_layers.Group(
                name=f"frame{f:03d}", layers=list(reversed(items)),
                closed=True, visible=group_visible,
            ))

        psd = nested_layers.nested_layers_to_psd(
            list(reversed(groups)),
            color_mode=enums.ColorMode.rgb,
            compression=comp_map[compression],
        )
        with open(output_path, "wb") as fh:
            psd.write(fh)

    def __repr__(self) -> str:
        return (f"LayerBean({self._width}x{self._height}, frames={self.num_frames}, "
                f"layers={self.total_layers})")


class LayerFileDecoder(object):
    """Decode Divoom 0x27 layer files into :class:`LayerBean` objects.

    Mirrors :class:`servoom.pixel_bean_decoder.PixelBeanDecoder`.
    """

    @staticmethod
    def decode_file(file_path: str) -> LayerBean:
        with open(file_path, "rb") as fp:
            return LayerFileDecoder.decode_stream(fp)

    @staticmethod
    def decode_stream(fp: IOBase) -> LayerBean:
        return LayerFileDecoder.decode_bytes(fp.read())

    @staticmethod
    def decode_bytes(data: bytes) -> LayerBean:
        if not data or data[0] not in SUPPORTED_FORMATS:
            got = f"0x{data[0]:02x}" if data else None
            raise ValueError(f"Not a Divoom layer file (0x27/0x28); first byte = {got}")
        fmt = data[0]

        # Stream 0 (the layer table) is a zstd stream in both formats.
        table_bytes, pos = LayerFileDecoder._read_zstd_stream(data, 1)
        frames_meta = LayerFileDecoder._parse_layer_table(table_bytes)
        total_layers = sum(f["num_layers"] for f in frames_meta)
        if total_layers == 0:
            raise ValueError("Layer file declares zero layers")

        # The pixel section differs between the two container versions.
        if fmt == FORMAT_RAW_RGB:
            bitmaps, side = LayerFileDecoder._bitmaps_from_raw_rgb(data, pos, total_layers)
        else:  # FORMAT_WEBP
            bitmaps, side = LayerFileDecoder._bitmaps_from_webp(data, pos, total_layers)

        frame_layers = []
        idx = 0
        for meta in frames_meta:
            n = meta["num_layers"]
            frame_layers.append(bitmaps[idx: idx + n])
            idx += n

        return LayerBean(
            width=side,
            height=side,
            frames_meta=frames_meta,
            frame_layers=frame_layers,
        )

    # -- internals ----------------------------------------------------------
    @staticmethod
    def _read_zstd_stream(data: bytes, pos: int) -> Tuple[bytes, int]:
        """Read one length-prefixed zstd stream at ``pos``; return ``(bytes, next_pos)``.

        Layout: ``uint32 compressed | uint32 uncompressed | <compressed zstd frame>``.
        """
        c = unpack(">I", data[pos: pos + 4])[0]
        u = unpack(">I", data[pos + 4: pos + 8])[0]
        comp = data[pos + 8: pos + 8 + c]
        if comp[:4] != ZSTD_MAGIC:
            raise ValueError(f"Expected zstd magic at offset {pos + 8}")
        dec = zstd.ZstdDecompressor().decompressobj().decompress(comp)
        if len(dec) != u:
            raise ValueError(f"Stream size mismatch: header {u}, decoded {len(dec)}")
        return dec, pos + 8 + c

    @staticmethod
    def _bitmaps_from_raw_rgb(data: bytes, pos: int, total_layers: int) -> Tuple[np.ndarray, int]:
        """0x27 pixels: one or more zstd streams of raw 24-bit RGB bitmaps (``K`` in all).

        The writer starts a new ``C | U | zstd`` stream every ~10 MB of raw bitmaps (cut at
        frame boundaries); small files have exactly one.
        """
        chunks = []
        while pos + 8 <= len(data):
            chunk, pos = LayerFileDecoder._read_zstd_stream(data, pos)
            chunks.append(chunk)
        pixel_bytes = b"".join(chunks)
        # Recover the square canvas side from the pixel-stream length.
        side = int(round(math.sqrt(len(pixel_bytes) / (3 * total_layers))))
        if side * side * 3 * total_layers != len(pixel_bytes):
            raise ValueError(
                f"Pixel stream ({len(pixel_bytes)} bytes) is not K*side^2*3 "
                f"(K={total_layers}); non-square canvas?"
            )
        bitmaps = np.frombuffer(pixel_bytes, dtype=np.uint8).reshape(
            total_layers, side, side, 3
        )
        return bitmaps, side

    @staticmethod
    def _bitmaps_from_webp(data: bytes, pos: int, total_layers: int) -> Tuple[np.ndarray, int]:
        """0x28 pixels: ``K`` records of ``[uint8 flag][uint32 BE length][lossless WEBP]``."""
        layers = []
        side = None
        for i in range(total_layers):
            if pos + 5 > len(data):
                raise ValueError(f"Truncated layer record {i} at offset {pos}")
            length = unpack(">I", data[pos + 1: pos + 5])[0]  # data[pos] is a reserved flag
            webp = data[pos + 5: pos + 5 + length]
            pos += 5 + length
            arr = np.array(Image.open(io.BytesIO(webp)).convert("RGB"), dtype=np.uint8)
            if side is None:
                side = arr.shape[0]
            if arr.shape != (side, side, 3):
                raise ValueError(
                    f"Layer {i}: expected {side}x{side} RGB bitmap, got {arr.shape}"
                )
            layers.append(arr)
        return np.stack(layers), side

    @staticmethod
    def _parse_layer_table(table: bytes) -> List[Dict]:
        pos = 0
        frames: List[Dict] = []
        while pos + 2 <= len(table):
            num_layers = table[pos]
            flag = table[pos + 1]
            pos += 2
            layers = []
            for _ in range(num_layers):
                desc = table[pos: pos + DESCRIPTOR_SIZE]
                pos += DESCRIPTOR_SIZE
                if len(desc) < DESCRIPTOR_SIZE:
                    raise ValueError("Layer table truncated inside a layer descriptor")
                layers.append({
                    "hidden": desc[0] != 0,   # byte[0]: nonzero => layer hidden
                    "opacity": desc[1],       # byte[1]: 0-255
                    # Editor HSL sliders, stored offset so they fit unsigned bytes.
                    "hue": unpack(">H", desc[2:4])[0] - 180,   # -180..180
                    "saturation": desc[4] - 100,               # -100..100
                    "lightness": desc[5] - 100,                # -100..100
                    "descriptor": desc.hex(),
                })
            frames.append({"num_layers": num_layers, "flag": flag,
                           "active_layer": flag, "layers": layers})
        if pos != len(table):
            raise ValueError(
                f"Layer table did not consume stream 0 exactly ({pos} != {len(table)})"
            )
        return frames
