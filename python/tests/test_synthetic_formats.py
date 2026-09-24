"""Synthetic-file tests for decoder paths the bundled reference assets don't cover.

The reference animations are all format-26 128x128 (the hierarchical ``Decoder0x1A``
path). These hand-built files exercise the other code paths touched by the de-dup:
the shared ``_frames_from_rgb`` (formats 42/43), the shared image compositor (format 43),
and the shared 0x0C decoder (format 26 @ 64x64 via ``AnimMulti64Decoder``).
"""

from __future__ import annotations

import io
import struct
from contextlib import redirect_stdout

import numpy as np
import zstandard
from PIL import Image

from servoom.pixel_bean_decoder import PixelBeanDecoder


def _decode(raw: bytes):
    with redirect_stdout(io.StringIO()):
        return PixelBeanDecoder.decode_stream(io.BytesIO(raw))


def test_format_42_zstd_raw_rgb_roundtrips_exactly():
    # 16x16 (row=1,col=1), two solid frames, zstd-compressed raw RGB.
    frame0 = bytes([10, 20, 30]) * 256
    frame1 = bytes([40, 50, 60]) * 256
    payload = zstandard.ZstdCompressor().compress(frame0 + frame1)
    raw = bytes([42]) + struct.pack(">BHBB", 2, 100, 1, 1) + payload

    bean = _decode(raw)
    assert bean.total_frames == 2
    assert (bean.width, bean.height) == (16, 16)
    assert np.array_equal(bean.frames_data[0], np.full((16, 16, 3), (10, 20, 30), np.uint8))
    assert np.array_equal(bean.frames_data[1], np.full((16, 16, 3), (40, 50, 60), np.uint8))


def test_format_43_embedded_gif_composites():
    # 16x16 two-frame GIF embedded in a format-43 container.
    imgs = [Image.new("RGB", (16, 16), (200, 10, 10)),
            Image.new("RGB", (16, 16), (10, 200, 10))]
    buf = io.BytesIO()
    imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:], duration=100, loop=0)
    raw = bytes([43]) + struct.pack(">BHBB", 2, 100, 1, 1) + buf.getvalue()

    bean = _decode(raw)
    assert bean.total_frames == 2
    assert (bean.width, bean.height) == (16, 16)
    for frame, expected in zip(bean.frames_data, [(200, 10, 10), (10, 200, 10)]):
        assert np.all(frame == frame[0, 0])  # uniform
        assert np.allclose(frame[0, 0], expected, atol=8)  # palette round-trip


def test_format_26_64x64_solid_0x0c_frame():
    # 64x64 (row=4,col=4) single solid-color frame via the 0x0C solid fast-path.
    frame_data = bytes([0xAA, 0x0B, 0x00, 0xF4, 0x01, 0x0C, 0x01, 0x00, 123, 45, 67])
    raw = (bytes([26]) + struct.pack(">BHBB", 1, 100, 4, 4)
           + struct.pack(">I", len(frame_data)) + frame_data)

    bean = _decode(raw)
    assert bean.total_frames == 1
    assert (bean.width, bean.height) == (64, 64)
    assert np.array_equal(bean.frames_data[0], np.full((64, 64, 3), (123, 45, 67), np.uint8))


def _aes(plain: bytes) -> bytes:
    from Crypto.Cipher import AES
    return AES.new(b"78hrey23y28ogs89", AES.MODE_CBC, b"1234567890123456").encrypt(plain)


def test_format_8_single_picture_is_one_raw_aes_frame():
    # Format 8 = [0x08] + AES-CBC(one raw 16x16 RGB frame): a still, no header at all.
    frame = b"".join(bytes([i & 0xFF, (i * 3) & 0xFF, 77]) for i in range(256))
    raw = bytes([8]) + _aes(frame)
    assert len(raw) == 769  # what every live sample measures

    bean = _decode(raw)
    assert bean.total_frames == 1
    assert (bean.width, bean.height) == (16, 16)
    assert bean.frames_data[0].tobytes() == frame
    assert _decode(bytes([8]) + _aes(frame)[:-16]) is None  # short payload -> None


def test_format_18_non_square_strip_places_tiles_row_major():
    # 1 row x 4 columns of 16x16 tiles (a 64x16 multi-panel strip), one LZO frame.
    import lzallright
    tiles = b"".join(bytes([t, 0, 0]) * 256 for t in range(4))
    comp = lzallright.LZOCompressor().compress(tiles)
    body = struct.pack(">I", len(comp)) + comp
    body += b"\x00" * (-len(body) % 16)
    raw = bytes([18]) + struct.pack(">BHBB", 1, 100, 1, 4) + _aes(body)

    bean = _decode(raw)
    assert (bean.width, bean.height) == (64, 16)
    for t in range(4):
        assert np.array_equal(bean.frames_data[0][:, t * 16:(t + 1) * 16],
                              np.full((16, 16, 3), (t, 0, 0), np.uint8))
