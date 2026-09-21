#!/usr/bin/env python
"""Generate tests/vectors.h: known-answer vectors for the C unit tests.

The Python library is the oracle, so the synthetic container files used by the C unit
tests are built here with the same helpers the Python tests use, decoded with the Python
decoders, and embedded together with the expected result. Re-run after changing the
Python decoders:

    python c/tests/gen_vectors.py
"""

from __future__ import annotations

import hashlib
import io
import struct
import sys
from contextlib import redirect_stdout
from pathlib import Path

import lzallright
import numpy as np
import zstandard as zstd
from Crypto.Cipher import AES
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "python"))
from servoom.layer_file_decoder import LayerFileDecoder  # noqa: E402
from servoom.pixel_bean_decoder import PixelBeanDecoder  # noqa: E402

out = []


def emit_bytes(name: str, data: bytes) -> None:
    out.append(f"static const unsigned char {name}[] = {{")
    for i in range(0, len(data), 16):
        out.append("    " + ", ".join(f"0x{b:02x}" for b in data[i:i + 16]) + ",")
    out.append("};")
    out.append(f"#define {name}_LEN {len(data)}")


def pixel_hash(raw: bytes) -> str:
    with redirect_stdout(io.StringIO()):
        bean = PixelBeanDecoder.decode_stream(io.BytesIO(raw))
    h = hashlib.sha256()
    for i in range(bean.total_frames):
        h.update(bean.frames_data[i].tobytes())
    return h.hexdigest(), bean


# --- LZO1X --------------------------------------------------------------------
lzo = lzallright.LZOCompressor()
lzo_cases = {
    "LZO_RAMP": bytes(range(256)) * 4,
    "LZO_REPEAT": b"abcabcabd" * 300 + b"\x00" * 1000 + bytes([7, 7, 7]) * 500,
    "LZO_RANDOM": bytes((i * 7919 + 13) & 0xFF for i in range(3000)),
    "LZO_SHORT": b"hello",
}
for name, raw in lzo_cases.items():
    emit_bytes(name + "_RAW", raw)
    emit_bytes(name + "_COMP", lzo.compress(raw))

# --- AES-CBC (Divoom key/iv) ---------------------------------------------------
plain = bytes(range(64))
cipher = AES.new(b"78hrey23y28ogs89", AES.MODE_CBC, b"1234567890123456")
emit_bytes("AES_PLAIN", plain)
emit_bytes("AES_CIPHER", cipher.encrypt(plain))

# --- synthetic containers (same builders as python/tests) ---------------------
# format 42: 16x16, two solid frames
frame0 = bytes([10, 20, 30]) * 256
frame1 = bytes([40, 50, 60]) * 256
raw42 = bytes([42]) + struct.pack(">BHBB", 2, 100, 1, 1) + zstd.ZstdCompressor().compress(frame0 + frame1)
h, bean = pixel_hash(raw42)
emit_bytes("FMT42_FILE", raw42)
out.append(f'#define FMT42_HASH "{h}"')

# format 43 with an embedded 2-frame GIF
imgs = [Image.new("RGB", (16, 16), (200, 10, 10)), Image.new("RGB", (16, 16), (10, 200, 10))]
buf = io.BytesIO()
imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:], duration=100, loop=0)
raw43 = bytes([43]) + struct.pack(">BHBB", 2, 100, 1, 1) + buf.getvalue()
h, bean = pixel_hash(raw43)
emit_bytes("FMT43_GIF_FILE", raw43)
out.append(f'#define FMT43_GIF_HASH "{h}"')

# format 43 with an embedded animated WebP (lossless, with alpha)
frames = []
for k in range(3):
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            if (x + y + k) % 3 == 0:
                im.putpixel((x, y), (x * 16, y * 16, k * 80, 255))
            elif (x + k) % 5 == 0:
                im.putpixel((x, y), (255, 0, 0, 128))
    frames.append(im)
buf = io.BytesIO()
frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0, lossless=True)
raw43w = bytes([43]) + struct.pack(">BHBB", 3, 100, 1, 1) + buf.getvalue()
h, bean = pixel_hash(raw43w)
emit_bytes("FMT43_WEBP_FILE", raw43w)
out.append(f'#define FMT43_WEBP_HASH "{h}"')

# format 26 64x64 solid 0x0C frame
frame_data = bytes([0xAA, 0x0B, 0x00, 0xF4, 0x01, 0x0C, 0x01, 0x00, 123, 45, 67])
raw26 = (bytes([26]) + struct.pack(">BHBB", 1, 100, 4, 4) + struct.pack(">I", len(frame_data)) + frame_data)
h, bean = pixel_hash(raw26)
emit_bytes("FMT26_SOLID_FILE", raw26)
out.append(f'#define FMT26_SOLID_HASH "{h}"')

# format 31: two 32x32 JPEG frames
buf = io.BytesIO()
jpegs = b""
for col in [(250, 10, 10), (10, 10, 250)]:
    im = Image.new("RGB", (32, 32), col)
    for x in range(32):
        im.putpixel((x, x), (0, 255, 0))
    b = io.BytesIO()
    im.save(b, format="JPEG", quality=85)
    jpegs += b.getvalue()
raw31 = bytes([31]) + struct.pack(">BHBB", 2, 100, 2, 2) + jpegs
h, bean = pixel_hash(raw31)
emit_bytes("FMT31_FILE", raw31)
out.append(f'#define FMT31_HASH "{h}"')

# format 17 (LZO + AES): 32x32 picture
img = np.zeros((32, 32, 3), np.uint8)
img[4:12, 4:12] = (200, 30, 30)
img[20:30, 16:28] = (30, 30, 200)
# tile order used by _compact for row=col=2: tiles (0,0),(1,0),(0,1),(1,1); pixels row-major in tile
tiles = b""
for gy in range(2):
    for gx in range(2):
        tiles += img[gy * 16:(gy + 1) * 16, gx * 16:(gx + 1) * 16].tobytes()
comp = lzo.compress(tiles)
plain = comp + b"\x00" * ((16 - len(comp) % 16) % 16)
enc = AES.new(b"78hrey23y28ogs89", AES.MODE_CBC, b"1234567890123456").encrypt(plain)
raw17 = bytes([17]) + struct.pack(">BBI", 2, 2, len(comp)) + enc
h, bean = pixel_hash(raw17)
assert np.array_equal(bean.frames_data[0], img)
emit_bytes("FMT17_FILE", raw17)
out.append(f'#define FMT17_HASH "{h}"')

# format 18 (per-frame LZO + AES): two 32x32 frames
records = b""
for f in range(2):
    fr = np.roll(img, f * 5, axis=1)
    tiles = b""
    for gy in range(2):
        for gx in range(2):
            tiles += fr[gy * 16:(gy + 1) * 16, gx * 16:(gx + 1) * 16].tobytes()
    comp = lzo.compress(tiles)
    records += struct.pack(">I", len(comp)) + comp
plain = records + b"\x00" * ((16 - len(records) % 16) % 16)
enc = AES.new(b"78hrey23y28ogs89", AES.MODE_CBC, b"1234567890123456").encrypt(plain)
raw18 = bytes([18]) + struct.pack(">BHBB", 2, 120, 2, 2) + enc
h, bean = pixel_hash(raw18)
emit_bytes("FMT18_FILE", raw18)
out.append(f'#define FMT18_HASH "{h}"')

# format 9: 16x16 three frames, AES over raw RGB
frames9 = b"".join(bytes([i * 40, 255 - i * 40, 7]) * 256 for i in range(3))
enc = AES.new(b"78hrey23y28ogs89", AES.MODE_CBC, b"1234567890123456").encrypt(frames9)
raw9 = bytes([9, 0]) + struct.pack(">H", 80) + enc
h, bean = pixel_hash(raw9)
assert bean.total_frames == 3 and bean.speed == 80
emit_bytes("FMT09_FILE", raw9)
out.append(f'#define FMT09_HASH "{h}"')


# --- layer files -----------------------------------------------------------------
def _layer_table(frames) -> bytes:
    b = bytearray()
    for layers in frames:
        b += bytes([len(layers), 0])
        for hidden, opacity in layers:
            b += bytes([1 if hidden else 0, opacity, 0, 0xB4, 0x64, 0x64])
    return bytes(b)


def _zstd_stream(raw: bytes) -> bytes:
    c = zstd.ZstdCompressor().compress(raw)
    return struct.pack(">I", len(c)) + struct.pack(">I", len(raw)) + c


SIDE = 16
l0 = np.zeros((SIDE, SIDE, 3), np.uint8); l0[2:6, 2:6] = (200, 10, 10)
l1 = np.zeros((SIDE, SIDE, 3), np.uint8); l1[8:12, 8:12] = (10, 200, 10)
l2 = np.zeros((SIDE, SIDE, 3), np.uint8); l2[4:10, 4:10] = (10, 10, 200)
frames_meta = [[(False, 255), (True, 128)], [(False, 200), (False, 77)]]
layers = [l0, l1, l1, l2]
raw27 = bytes([0x27]) + _zstd_stream(_layer_table(frames_meta)) + _zstd_stream(b"".join(l.tobytes() for l in layers))
raw28 = bytearray([0x28]) + _zstd_stream(_layer_table(frames_meta))
for layer in layers:
    b = io.BytesIO()
    Image.fromarray(layer, "RGB").save(b, format="WEBP", lossless=True)
    w = b.getvalue()
    raw28 += bytes([0]) + struct.pack(">I", len(w)) + w
raw28 = bytes(raw28)


def layer_summary(raw: bytes):
    layer = LayerFileDecoder.decode_bytes(raw)
    comp = hashlib.sha256()
    for i in range(layer.num_frames):
        comp.update(layer.composite_frame(i).tobytes())
    rawh = hashlib.sha256()
    for i in range(layer.num_frames):
        rawh.update(layer.frame_layers(i).tobytes())
    return layer, comp.hexdigest(), rawh.hexdigest()


for name, raw in (("LAYER27", raw27), ("LAYER28", raw28)):
    layer, ch, rh = layer_summary(raw)
    emit_bytes(name + "_FILE", raw)
    out.append(f'#define {name}_HASH "{ch}"')
    out.append(f'#define {name}_LAYERS_HASH "{rh}"')
    out.append(f"#define {name}_FRAMES {layer.num_frames}")
    out.append(f"#define {name}_TOTAL_LAYERS {layer.total_layers}")

header = ["/* AUTO-GENERATED by tests/gen_vectors.py -- do not edit. */",
          "#ifndef SERVOOM_TEST_VECTORS_H", "#define SERVOOM_TEST_VECTORS_H", ""]
(HERE / "vectors.h").write_text("\n".join(header + out + ["", "#endif", ""]), "utf-8", newline="\n")
print(f"wrote {HERE / 'vectors.h'}")
