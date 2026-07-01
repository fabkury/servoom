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

* **layer table**: for each animation frame ``uint8 num_layers``, ``uint8 flag``
  (unconfirmed; likely the editor's active-layer index), then ``num_layers`` x 6-byte
  descriptors where ``byte[0]`` is the HIDDEN flag (nonzero => layer hidden, excluded from
  the composite) and ``byte[1]`` is the layer OPACITY (0-255). ``K`` = sum of ``num_layers``.

* **pixels, format 0x27**: a *second* length-prefixed zstd stream holding ``K`` layer
  bitmaps, each ``side*side*3`` bytes of raw 24-bit RGB, frame-major (bottom -> top). The
  canvas is square, so ``side = sqrt(len(stream1) / (3*K))``.
* **pixels, format 0x28**: ``K`` records, each ``uint8 flag`` (reserved; observed 0),
  ``uint32 BE length``, then a lossless **WEBP** image of the layer bitmap (RGB, black =
  transparent, same as 0x27). ``side`` comes from the WEBP dimensions.

Compositing (matches the app): the colour black ``(0,0,0)`` is transparent; layers are
painted bottom -> top over a black canvas and alpha-blended with ``opacity/255``.

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
        """Alpha-composite ``frame`` (black = transparent, bottom -> top) to ``(H, W, 3)``.

        Layers flagged hidden (descriptor ``byte[0]`` nonzero) are skipped.
        """
        layers = self._frame_layers[frame]
        metas = self._frames_meta[frame]["layers"]
        canvas = np.zeros((self._height, self._width, 3), dtype=float)
        for layer, meta in zip(layers, metas):
            if meta["hidden"]:
                continue
            alpha = meta["opacity"] / 255.0
            mask = np.any(layer != 0, axis=2)  # non-black pixels are painted
            canvas[mask] = layer[mask].astype(float) * alpha + canvas[mask] * (1.0 - alpha)
        return np.clip(np.round(canvas), 0, 255).astype(np.uint8)

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

        Stacking is bottom -> top: frame 0 is the bottom-most group and, within each
        frame, layer 0 is the bottom-most layer -- matching the Divoom paint order.

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

        def _image_layer(name, rgb, opacity, visible):
            # Divoom treats black (0,0,0) as transparent -> derive an alpha channel.
            alpha = (np.any(rgb != 0, axis=2).astype(np.uint8)) * 255
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
        groups = []
        for f in range(self.num_frames):
            items = []
            for li, meta in enumerate(self._frames_meta[f]["layers"]):
                rgb = self._frame_layers[f][li]
                tag = "_HIDDEN" if meta["hidden"] else ""
                name = f"f{f:03d}_l{li:02d}_op{meta['opacity']:03d}{tag}"
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
        """0x27 pixels: a single zstd stream of ``K`` raw 24-bit RGB bitmaps."""
        pixel_bytes, _ = LayerFileDecoder._read_zstd_stream(data, pos)
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
                layers.append({
                    "hidden": desc[0] != 0,   # byte[0]: nonzero => layer hidden
                    "opacity": desc[1],       # byte[1]: 0-255
                    "descriptor": desc.hex(),
                })
            frames.append({"num_layers": num_layers, "flag": flag, "layers": layers})
        if pos != len(table):
            raise ValueError(
                f"Layer table did not consume stream 0 exactly ({pos} != {len(table)})"
            )
        return frames
