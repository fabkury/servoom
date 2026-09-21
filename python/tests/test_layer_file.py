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


def _read_psd_groups(fh):
    """Return the PSD's top-level groups as bottom -> top (pytoshop lists top first).

    ``fh`` must stay open while the result is used: pytoshop reads channel pixels lazily.
    """
    pytoshop = pytest.importorskip("pytoshop")
    from pytoshop.user import nested_layers

    return list(reversed(nested_layers.psd_to_nested_layers(pytoshop.read(fh))))


def _channel(layer, idx) -> np.ndarray:
    return np.asarray(layer.channels[idx].image)


@pytest.mark.parametrize("all_frames_visible", [True, False], ids=["all-visible", "frame0-only"])
def test_save_to_psd_structure(tmp_path, all_frames_visible):
    pytest.importorskip("pytoshop")
    l0, l1 = _sample_layers()
    # frame 0: opaque red + hidden half-opacity green; frame 1: green at opacity 200.
    frames = [[(False, 255), (True, 128)], [(False, 200)]]
    layer = LayerFileDecoder.decode_bytes(_build_0x27(frames, [l0, l1, l1]))

    out = tmp_path / "out.psd"
    layer.save_to_psd(str(out), all_frames_visible=all_frames_visible)
    with open(out, "rb") as fh:
        _check_psd_structure(_read_psd_groups(fh), frames, l0, l1, all_frames_visible)


def _check_psd_structure(groups, frames, l0, l1, all_frames_visible):

    # One group per frame, frame 0 at the bottom; visibility follows all_frames_visible.
    assert [g.name for g in groups] == ["frame000", "frame001"]
    assert [g.visible for g in groups] == [True, all_frames_visible]

    expected_names = [
        ["f000_bg", "f000_l00_op255", "f000_l01_op128_HIDDEN"],
        ["f001_bg", "f001_l00_op200"],
    ]
    expected_sources = [[None, l0, l1], [None, l1]]
    for group, names, sources, meta in zip(groups, expected_names, expected_sources, frames):
        layers = list(reversed(group.layers))  # bottom -> top
        assert [l.name for l in layers] == names
        for psd_layer in layers:
            assert (psd_layer.top, psd_layer.left, psd_layer.bottom, psd_layer.right) == (0, 0, SIDE, SIDE)

        # Black is the chroma key: every group sits on an opaque, visible black background.
        bg = layers[0]
        assert bg.visible and bg.opacity == 255
        for ch in (0, 1, 2):
            assert not _channel(bg, ch).any()
        assert np.all(_channel(bg, -1) == 255)

        # Divoom layers keep their RGB, opacity and hidden flag; black -> alpha 0.
        for psd_layer, src, (hidden, opacity) in zip(layers[1:], sources[1:], meta):
            rgb = np.dstack([_channel(psd_layer, ch) for ch in (0, 1, 2)])
            assert np.array_equal(rgb, src)
            painted = np.any(src != 0, axis=2)
            assert np.array_equal(_channel(psd_layer, -1) == 255, painted)
            assert psd_layer.opacity == opacity
            assert psd_layer.visible is (not hidden)
