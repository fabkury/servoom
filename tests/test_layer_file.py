"""Tests for the Divoom layer-file decoder (container formats 0x27 and 0x28).

The reference assets don't include a layer file, so these build tiny synthetic ones for
both container versions:

* **0x27** — pixels are one zstd stream of raw 24-bit RGB bitmaps.
* **0x28** — pixels are per-layer lossless-WEBP records (the newer format that regressed;
  see the layer file of gallery 4200665, "Dostoyevsky's Transformation").
"""

from __future__ import annotations

import io
import struct

import numpy as np
import pytest
import zstandard as zstd
from PIL import Image

from servoom.layer_file_decoder import LayerFileDecoder

SIDE = 16


def _layer_table(frames) -> bytes:
    """frames: list of list of (hidden, opacity) -> raw layer-table bytes."""
    out = bytearray()
    for layers in frames:
        out += bytes([len(layers), 0])  # num_layers, flag
        for hidden, opacity in layers:
            out += bytes([1 if hidden else 0, opacity, 0, 0xB4, 0x64, 0x64])
    return bytes(out)


def _zstd_stream(raw: bytes) -> bytes:
    comp = zstd.ZstdCompressor().compress(raw)
    return struct.pack(">I", len(comp)) + struct.pack(">I", len(raw)) + comp


def _sample_layers():
    l0 = np.zeros((SIDE, SIDE, 3), np.uint8); l0[2:6, 2:6] = (200, 10, 10)
    l1 = np.zeros((SIDE, SIDE, 3), np.uint8); l1[8:12, 8:12] = (10, 200, 10)
    return l0, l1


def _build_0x27(frames, layers) -> bytes:
    raw = b"".join(l.tobytes() for l in layers)
    return bytes([0x27]) + _zstd_stream(_layer_table(frames)) + _zstd_stream(raw)


def _build_0x28(frames, layers) -> bytes:
    out = bytearray([0x28]) + _zstd_stream(_layer_table(frames))
    for layer in layers:
        buf = io.BytesIO()
        Image.fromarray(layer, "RGB").save(buf, format="WEBP", lossless=True)
        webp = buf.getvalue()
        out += bytes([0]) + struct.pack(">I", len(webp)) + webp  # flag, length, image
    return bytes(out)


@pytest.mark.parametrize("build", [_build_0x27, _build_0x28], ids=["0x27", "0x28"])
def test_layer_file_decodes_both_formats(build):
    l0, l1 = _sample_layers()
    frames = [[(False, 255)], [(False, 128)]]  # 2 frames, 1 layer each
    bean = build(frames, [l0, l1])

    layer = LayerFileDecoder.decode_bytes(bean)
    assert (layer.width, layer.height) == (SIDE, SIDE)
    assert layer.num_frames == 2 and layer.total_layers == 2
    assert np.array_equal(layer.frame_layers(0)[0], l0)
    assert np.array_equal(layer.frame_layers(1)[0], l1)

    # frame 0 is a fully-opaque red square on black; composite reproduces the layer.
    assert np.array_equal(layer.composite_frame(0), l0)
    # frame 1 is 50% opacity: painted pixels are halved toward black.
    comp1 = layer.composite_frame(1)
    assert comp1[9, 9].tolist() == [round(10 * 128 / 255), round(200 * 128 / 255), round(10 * 128 / 255)]


def test_hidden_layer_excluded_from_composite():
    l0, l1 = _sample_layers()
    frames = [[(False, 255), (True, 255)]]  # one frame: layer1 hidden
    layer = LayerFileDecoder.decode_bytes(_build_0x28(frames, [l0, l1]))
    comp = layer.composite_frame(0)
    assert np.array_equal(comp, l0)  # hidden l1 (green) must not appear
    assert not np.any(np.all(comp == (10, 200, 10), axis=-1))


def test_rejects_non_layer_file():
    with pytest.raises(ValueError, match=r"0x27/0x28"):
        LayerFileDecoder.decode_bytes(bytes([0x1A, 0, 0, 0, 0]))
