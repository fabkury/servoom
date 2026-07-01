"""
Decoder for Divoom LAYER files (container format 0x27 / 39).

A Divoom layer file (referenced by ``LayerFileId`` in gallery metadata) is the editable,
layered source for an artwork; the artwork file (``FileId``) is the flattened render.
This module recovers every layer bitmap, the per-frame layer structure and per-layer
opacity, and can re-composite the animation the way the Divoom editor does.

Container layout (big-endian integers)::

    offset 0 : uint8   format id = 0x27 (39)
    then, repeated, a length-prefixed zstd stream:
        uint32  C     compressed size
        uint32  U     uncompressed size
        bytes[C]      one zstd frame (magic 28 B5 2F FD) -> U bytes

There are exactly two streams:

* **stream 0 - layer table**: for each animation frame ``uint8 num_layers``,
  ``uint8 flag`` (unconfirmed; likely the editor's active-layer index), then
  ``num_layers`` x 6-byte descriptors whose ``byte[1]`` is the layer OPACITY (0-255).
* **stream 1 - pixels**: ``K`` layer bitmaps, each ``side*side*3`` bytes of raw 24-bit
  RGB, ordered frame-major (bottom -> top). The canvas is square, so
  ``side = sqrt(len(stream1) / (3*K))``.

Compositing (matches the app): the colour black ``(0,0,0)`` is transparent; layers are
painted bottom -> top over a black canvas and alpha-blended with ``opacity/255``.

See ``sandbox/divoom-recommended-metadata/LAYER_FORMAT_FINDINGS.md`` for the full
reverse-engineering write-up and validation.
"""

import math
from io import IOBase
from struct import unpack
from typing import Dict, List, Optional

import numpy as np
import zstandard as zstd

from .pixel_bean import PixelBean

FORMAT_ID = 0x27
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
        """Alpha-composite ``frame`` (black = transparent, bottom -> top) to ``(H, W, 3)``."""
        layers = self._frame_layers[frame]
        opacities = [ly["opacity"] for ly in self._frames_meta[frame]["layers"]]
        canvas = np.zeros((self._height, self._width, 3), dtype=float)
        for layer, opacity in zip(layers, opacities):
            alpha = opacity / 255.0
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
        if not data or data[0] != FORMAT_ID:
            got = data[0] if data else None
            raise ValueError(f"Not a Divoom layer file (0x27); first byte = {got!r}")

        streams = LayerFileDecoder._read_streams(data)
        if len(streams) != 2:
            raise ValueError(f"Expected 2 zstd streams, found {len(streams)}")
        streams_meta = [(c, u) for (c, u, _) in streams]
        table_bytes = streams[0][2]
        pixel_bytes = streams[1][2]

        frames_meta = LayerFileDecoder._parse_layer_table(table_bytes)
        total_layers = sum(f["num_layers"] for f in frames_meta)
        if total_layers == 0:
            raise ValueError("Layer file declares zero layers")

        # Recover the square canvas side from the pixel-stream length.
        area = len(pixel_bytes) / (3 * total_layers)
        side = int(round(math.sqrt(area)))
        if side * side * 3 * total_layers != len(pixel_bytes):
            raise ValueError(
                f"Pixel stream ({len(pixel_bytes)} bytes) is not K*side^2*3 "
                f"(K={total_layers}); non-square canvas?"
            )

        bitmaps = np.frombuffer(pixel_bytes, dtype=np.uint8).reshape(
            total_layers, side, side, 3
        )
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
            streams_meta=streams_meta,
        )

    # -- internals ----------------------------------------------------------
    @staticmethod
    def _read_streams(data: bytes):
        """Return list of ``(compressed_size, uncompressed_size, decompressed_bytes)``."""
        pos = 1
        dctx = zstd.ZstdDecompressor()
        out = []
        while pos + 8 <= len(data):
            c = unpack(">I", data[pos: pos + 4])[0]
            u = unpack(">I", data[pos + 4: pos + 8])[0]
            comp = data[pos + 8: pos + 8 + c]
            if comp[:4] != ZSTD_MAGIC:
                raise ValueError(f"Expected zstd magic at offset {pos + 8}")
            dec = dctx.decompressobj().decompress(comp)
            if len(dec) != u:
                raise ValueError(f"Stream size mismatch: header {u}, decoded {len(dec)}")
            out.append((c, u, dec))
            pos += 8 + c
        return out

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
                layers.append({"opacity": desc[1], "descriptor": desc.hex()})
            frames.append({"num_layers": num_layers, "flag": flag, "layers": layers})
        if pos != len(table):
            raise ValueError(
                f"Layer table did not consume stream 0 exactly ({pos} != {len(table)})"
            )
        return frames
