# Divoom "Layer File" format (0x27 / 39, 0x28 / 40 and the older 0x1D / 29) — reverse-engineering findings

Status: **format essentially solved.** The decoder
(`divoom_layer_decoder.py` here, and `servoom.LayerFileDecoder` in the package) parses the
container, recovers every layer bitmap and per-layer opacity, and re-composites the
animation. Validated against 20 layer/artwork pairs sampled from the Recommended gallery
(0x27), plus one 0x28 sample, whose
composite matches the artwork render to within ~0.9 avg RGB. The previous generation of
the container, `0x1D` (files dated 2023-01 .. 2024-12), is described in §1b and was
validated against 305 layer/artwork pairs of one artist (§5b).

The layer file is the **editable, layered source** the Divoom app keeps for an artwork
(field `LayerFileId`). The artwork file (`FileId`) is the flattened render.

---

## 1. Container layout

All multi-byte integers are **big-endian**. Two current container versions exist; they
share the same layer table and differ only in how the pixels are stored. The older
`0x1D` container (§1b) uses the same 6-byte descriptors but a different wrapping.

```
offset 0 : uint8   format id = 0x27 (39)  or  0x28 (40)
STREAM 0 (both): a length-prefixed zstd stream = the LAYER TABLE
     uint32  C     compressed size of this stream (bytes)
     uint32  U     uncompressed size of this stream (bytes)
     bytes[C]      one zstd frame (magic 28 B5 2F FD) that inflates to U bytes
```

Pixels follow the layer table, encoded by format id:

| Format | Pixel section                                                              |
|-------:|----------------------------------------------------------------------------|
| 0x27   | a **second** zstd stream: K raw 24-bit RGB bitmaps, concatenated            |
| 0x28   | K records, each `[uint8 flag][uint32 BE length][lossless WEBP]` (one/layer) |

For 0x27 the first 9 bytes are `27 | C0(4) | U0(4)`, then zstd stream 0, then
`C1(4) | U1(4)`, then zstd stream 1 (held for all 20 samples, 0 trailing bytes). For 0x28
the layer-table stream is followed by K length-prefixed WEBP records that consume the file
exactly (the `flag` byte was 0x00 for all 92 layers in the sample; treated as reserved).

Compression is **zstd** for the table (same codec as artwork format 0x2A / 42); 0x28 stores
each layer bitmap as a **lossless WEBP** (VP8L). No AES and no LZO in the layer container.

---

## 1b. The 0x1D (29) container — the 2023–2024 generation

Layer files uploaded between January 2023 and December 2024 begin with `0x1D` (in the
request-04 archive: 305 files, 2023-01-07 .. 2024-12-24, while the same artist's 0x27/0x28
files start on 2025-04-01). App 3.8.40 still reads it: its `unPackLayerDataOther` branch
also accepts the relatives `0x18`, `0x1B`, `0x1C`, `0x20` and `0x24`, none of which has
been seen in the wild. Resolved 2026-11-04 from that reader and the archive.

```
offset 0  : uint8   format id = 0x1D (29)
offset 1  : uint32  E   bytes of the stream that are AES-encrypted (0x60 = 96 in every file)
offset 5  : uint32  Z   length of the zlib stream
offset 9  : uint32  R   inflated size of the payload
offset 13 : bytes[E]    AES-128-CBC ciphertext, key "78hrey23y28ogs89", IV "1234567890123456"
                        (the artwork-file key), no padding -> the first E bytes of the stream
offset 13+E : the remaining Z-E bytes of the stream, in the clear
```

The file is exactly `13 + Z` bytes long. Decrypted head + plain tail form a zlib stream
(`78 9C`) that inflates to `R` bytes, the **payload**, in which the layer table and the
pixels are interleaved:

```
per frame:
    uint8  num_layers
    uint8  active_layer          (same meaning as §2)
    num_layers x:
        6-byte layer descriptor  (identical to §2: hidden, opacity, hue+180, sat+100, lit+100)
        side*side*3 bytes        the layer's 24-bit RGB bitmap, immediately after its descriptor
```

Bitmaps are **tile-ordered**, the device's native order: the canvas is split into 16x16
tiles, tiles row-major, and inside a tile 16 rows of 16 RGB pixels (48 bytes per row).
The app un-tiles on load; 16x16 canvases are unaffected. Frames are bottom → top as in
the current containers, and the frame count always equalled the artwork's (305/305).

**There is no size field.** The reader takes the canvas size from the gallery record, but
the archive's `FileSize` is wrong for 3 of the 305 files (it says 16x16 for a 32x32
single-frame layer source whose published artwork is 16x16). The decoders therefore
*detect* the side: the payload is parsed at 16, 32, 64, 128 and 256 and the side at which
it is consumed exactly wins. A wrong side can also consume the payload exactly (12 of 305,
pixel bytes read as frame headers), but then the "descriptors" are garbage — a hidden
byte above 1, a hue above 360, an active-layer index past the layer count, or frames with
zero layers — and those parses are rejected. With that rule all 305 files resolve to a
single side; a `side` hint is honoured when it parses.

Descriptor values seen in the 305 files: hidden byte `00` (23,348 layers) or `01` (704);
1,179 layers carry non-neutral HSL sliders; opacity 0..255.

---

## 2. Stream 0 — the layer table

A flat sequence of per-frame records, one record per animation frame, read until the
stream is exhausted:

```
per frame:
    uint8  num_layers        number of layers in this frame
    uint8  active_layer      index of the layer last selected in the editor (0-based)
    num_layers x 6-byte layer descriptor:
        byte[0]  HIDDEN       nonzero => layer hidden (skip it)
        byte[1]  OPACITY      0..255
        uint16   HUE + 180    big-endian; hue slider -180..180  (neutral 0x00B4)
        byte[4]  SAT + 100    saturation slider -100..100       (neutral 0x64)
        byte[5]  LIT + 100    lightness slider  -100..100       (neutral 0x64)
```

Cross-checks that all passed on the full sample:

* number of frame records **== the artwork's declared frame count**;
* `sum(num_layers)` over all frames **== K**, the number of bitmaps in stream 1;
* the parse consumes stream 0 **exactly** (no leftover bytes).

**`active_layer`** (previously "flag") is the index of the layer that was selected in the
editor when the file was saved; it takes values 0..8 in the sample and is irrelevant for
rendering. Writers may emit 0.

**Descriptor byte [0] = hidden flag** (CONFIRMED): nonzero means the layer is hidden in
the editor and must be **excluded** from the composite. Only 7 of 1814 layers in the
first sample were hidden (`0x01`), all in pair-01 (4) and pair-03 (3). Skipping them
makes both pairs reconstruct exactly and regresses nothing. This was found because
pair-01's first frame showed extra pixels that were absent from the rendered artwork.

**Descriptor byte [1] = opacity** is confirmed empirically (see §5): using it as an
alpha value is what makes multi-layer frames reconstruct. Values observed: 0, 6, 26, 28,
… 227, 233, 255. `0` = fully transparent layer; `255` = fully opaque.

**Descriptor bytes [2:6] = the layer's HSL sliders** (resolved 2026-10-21). The editor's
per-layer Hue / Saturation / Lightness adjustment is remembered as three offset
integers: hue + 180 as a big-endian `uint16`, saturation + 100 and lightness + 100 as
single bytes, so the neutral descriptor tail is `00 B4 64 64`. About one layer in ten in
the wild carries a non-neutral value (e.g. `01 68 64 64` = hue +180, `00 B4 C4 04` =
saturation +96 / lightness -96).

The sliders are **applied at render time** by the Android app (3.8.40): the stored bitmap
is the un-adjusted paint, and every painted (non-black) pixel of the layer goes through
an integer HSL adjustment before it is blended (§4). Only *painted* (non-black) pixels
are adjusted: a transparent pixel must not light up when the lightness slider is raised.
With that rule, all 34 corpus files with HSL layers (lossy 16px artworks excluded)
reproduce the flattened artwork; ignoring the sliders breaks 33 of them (in the 34th the
adjusted layer is invisible either way). The
decoders follow the Android app (apply), expose the values (`hue`, `saturation`,
`lightness`), and the PSD export appends `_hue<h>_sat<s>_lit<l>` to the layer name when
any of the three is non-zero.

---

## 3. The pixel data

Bitmaps are ordered **frame-major** in both formats: all layers of frame 0 (bottom → top),
then all layers of frame 1, and so on.

**0x27 — raw RGB (stream 1).** `K` bitmaps laid out back-to-back, each `side*side*3` bytes,
row-major, **8 bits per channel RGB** (24-bit). This directly confirms the app's internal
24-bit RGB model (smooth gradients survive round-trips). The canvas is square, so the side
length is recoverable from the file alone: `side = sqrt( U1 / (3*K) )` — integral for every
sample (16, 32, 64, 128, 256); the layer file needs **no external size hint**.

**0x28 — lossless WEBP.** Each layer bitmap is a standalone **VP8L (lossless) WEBP** image,
preceded by a `uint8` flag (0x00, reserved) and a `uint32` big-endian byte length. Decoding
each WEBP to RGB yields the same 24-bit layer bitmap as 0x27; the side comes from the WEBP
dimensions. Same black-as-transparent convention (no alpha channel is used).

---

## 4. Compositing rule (matches the Divoom editor)

* **Black `(0,0,0)` is transparent.** (Confirmed by the user; visible in the data — e.g.
  empty background layers are entirely `(0,0,0)`.)
* Layers are painted **bottom → top** over a black canvas; hidden layers are skipped.
* If a layer's HSL sliders are not all zero, each painted pixel is first adjusted
  (single-precision RGB→HSL quantised to `h` 0..359 / `s`,`l` 0..100 by truncation;
  `h += hue` wrapped; a negative saturation/lightness scales `s`/`l` by `1 + v/100`
  (truncated), a positive one is added, `s` only when it was non-zero; clamp to 0..100;
  HSL→RGB, each channel truncated to 0..255). A pixel that becomes black is transparent.
* Each painted pixel is then **alpha-blended** with `alpha = opacity / 255` in single
  precision and **truncated** (not rounded) to an integer canvas value:

```
for each layer L (bottom -> top) with opacity op:
    a = float32(op / 255)
    for each pixel p where L[p] != (0,0,0):     # non-black = painted (after HSL)
        canvas[p] = trunc( float32(L[p]*a) + float32(canvas[p]*(1-a)) )
```

With this rule frames without HSL layers reproduce the flattened artwork **exactly**
(mean error 0.001 over 35 corpus files whose artwork decoder is lossless), where the
earlier round-to-nearest blend left a ±1 residual.

**Two HSL pipelines (0x1D era).** The integer pipeline above is what app 3.8.40 renders
and what every 0x27/0x28 file checked so far was flattened with. Among the 0x1D files it
reproduces the artworks dated up to 2023-06-10 exactly, but *every* HSL layer in files
from 2023-06-20 on comes out ±2..8 off. Those artworks were flattened by an app that kept
`h` (degrees), `s` and `l` as floats: same RGB→HSL, `h += hue` wrapped, a negative
saturation/lightness scales `s`/`l` by `1 + v/100`, a positive one adds `v/100` (`s` only
when non-zero), clamp to 0..1, HSL→RGB, truncate each channel. Measured on a gray 122
with lightness −20: the float pipeline gives 97 (122/255·0.8 → 97.6), the quantised one
94 (47% → 37%). The decoders keep the integer pipeline as the default (it is the current
app's behaviour) and expose the other as `adjust_hsl_float` / `hsl_mode="float"`. A few
hue-only pixels still differ by ±1 under the float pipeline (e.g. (218,122,102) with hue
−12 renders G=102, our float32 chain yields 101): the exact order of operations of that
app is not known.

---

## 5. Validation (20 pairs, 477 frames)

Reconstructed frames were compared to the artwork frames produced by servoom's *artwork*
decoder (`PixelBeanDecoder`). That decoder is itself lossy (±1 quantization, occasional
per-frame glitches, and it under-counts frames), so it is a soft reference — agreement to
its quantization floor is a pass.

Numbers below are **with the hidden-flag fix applied** (skip layers where byte[0] != 0):

| Match tolerance | Frames | %     |
|-----------------|-------:|------:|
| exact           | 256    | 53.7  |
| within ±4       | **461**| **96.6** |

Key points:

* **Single-layer frames match the artwork EXACTLY** (byte-for-byte) wherever the artwork
  decoder is trustworthy — the cleanest possible confirmation that stream 1 is correct.
* Honoring the hidden flag makes **pair-01 (64/64) and pair-03 (5/5) reconstruct
  exactly** — before the fix their hidden layers leaked extra pixels into the composite.
* The `±1`…`±4` residual (e.g. pair-11, pair-20) is the **artwork decoder's** palette
  quantization, not a layer-model error. pair-11 goes from maxdiff 132 (opacity ignored)
  to maxdiff **4** (opacity applied) — opacity is real and necessary.
* The only remaining large disagreements are pair-09 / pair-19 (16×16, artwork
  **format 9**). There the layer composite is a clean, coherent image and the
  **format-9 artwork decoder** is the suspect party (it mis-colors those files while
  working on others). Worth a follow-up against a ground-truth render from the app.
* Bonus: the layer file often carries **more frames than the artwork decoder emits**
  (e.g. pair-17: 92 vs 69; pair-07: 55 vs 33), so it is the **more faithful** source of
  the true frame count.

---

## 5b. Validation of the 0x1D container (305 files, one artist)

Every `0x1D` layer file of request 04 (requests/04-thepixelxb) was decoded, composited
and compared byte-for-byte with the raw frames of its flattened artwork (decoded by
`PixelBeanDecoder`; the WebP next to it is not the reference because libwebp merges
identical frames). Script: `requests/04-thepixelxb/validate_0x1d.py`.

| Outcome                                              | Files |
|------------------------------------------------------|------:|
| decoded (payload parses, side resolved)              | 305   |
| composite == artwork, integer HSL pipeline           | 238   |
| composite == artwork, float HSL pipeline             | 257   |
| composite == artwork, pipeline chosen by upload date | 263   |
| **composite == artwork with either pipeline**        | **263** |
| ±1..8 residue on HSL layers only (float32 details)   | 17    |
| artwork re-rendered after the layer file was saved   | 21    |
| artwork is lossy (format 31, JPEG)                   | 1     |
| artwork is a different size (16x16 render of a 32x32 source) | 3 |

Per canvas: 16x16 133/140, 32x32 28/39, 64x64 71/80, 128x128 31/46 exact. The 21
"re-rendered" files are not decoder errors: their differing frames are reordered, have
pixels painted that the layer file lacks, or differ in frames without any slider (one
single-layer, fully opaque frame at 128x128 differs in 10,298 pixels) — the artist edited
and re-published the artwork without the layer file following.

---

## 6. Tooling

The finalized decoders built from these findings:

* `servoom.LayerFileDecoder` / `servoom.LayerBean` (Python package) — decode a layer file
  (0x1D, 0x27 or 0x28; `LayerBean.format` says which) and export a composited WebP
  (`save_to_webp`) or a layered PSD (`save_to_psd`). `composite_frame(..., hsl_mode=)`
  selects the HSL pipeline (§4).
  In the PSD, each frame is a group (`frameNNN`) whose bottom-most layer is an opaque
  black background (`fNNN_bg`): black is the chroma key, so pixels transparent in every
  layer must still render black, as in the app. Above it come the Divoom layers
  (`fNNN_lLL_opOOO[_hueH_satS_litL][_HIDDEN]`) with black mapped to alpha 0.
* `docs/src/lib/layerFile.ts` — the same decode + PSD export in the browser (used by the
  web app at servoom.pages.dev); produces the same layer structure.
* `layer-tools/divoom_layer_decoder.py` — self-contained CLI (needs only the `.dat`;
  deps: numpy, zstandard, pillow):
  * `python divoom_layer_decoder.py <layer.dat> --out DIR [--layers]`
  * `python divoom_layer_decoder.py --batch <dir-of-pair-*/layer.dat> --out DIR`
  * exports `composited.webp` (lossless) and, with `--layers`, one PNG per layer named
    `frameNNN_layerLL_opOOO.png`.
* `layer-tools/layers_to_psd.py` — CLI wrapper over the package that converts a layer file
  (or a `--batch` directory) into layered PSD(s).

---

## 7. Open questions / next steps

1. ~~Descriptor bytes [2:6] and the per-frame flag~~ — resolved (§2): HSL sliders and
   the active-layer index. The 0x28 per-record flag byte selects the record codec:
   `0` = lossless WEBP (the only value seen in the wild); nonzero = a zstd frame whose
   uncompressed size is one layer bitmap. A 0x27 pixel section may also hold **several**
   consecutive `C | U | zstd` streams (the writer starts a new one every ~10 MB of raw
   bitmaps, cutting only at frame boundaries); every file sampled so far fits in one.
2. Ground-truth colours: validate pair-09/19 against an actual app/web render rather than
   the format-9 artwork decoder.
3. Frame duration/speed: **not** present in the layer file (header speed bytes are 0);
   it lives in the artwork file. The layer decoder defaults to 100 ms/frame.
4. Non-square canvases: unverified (all Divoom sizes in this sample are square); the
   `sqrt` size recovery assumes square, and the 0x1D size detection only tries square
   canvases.
5. The float HSL pipeline of the 2023-06 .. 2024 app (§4) is reproduced to ±1 on a few
   hue-only pixels; the exact float order of operations is unknown. The other 0x1D
   relatives app 3.8.40 reads (`0x18`, `0x1B`, `0x1C`, `0x20`, `0x24`) have no samples.
