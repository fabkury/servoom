# Divoom "Layer File" format (0x27 / 39 and 0x28 / 40) — reverse-engineering findings

Status: **format essentially solved.** The decoder
(`divoom_layer_decoder.py` here, and `servoom.LayerFileDecoder` in the package) parses the
container, recovers every layer bitmap and per-layer opacity, and re-composites the
animation. Validated against 20 layer/artwork pairs sampled from the Recommended gallery
(0x27), plus the 0x28 variant (gallery 4200665, "Dostoyevsky's Transformation"), whose
composite matches the artwork render to within ~0.9 avg RGB.

The layer file is the **editable, layered source** the Divoom app keeps for an artwork
(field `LayerFileId`). The artwork file (`FileId`) is the flattened render.

---

## 1. Container layout

All multi-byte integers are **big-endian**. Two container versions exist; they share the
same layer table and differ only in how the pixels are stored.

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

## 2. Stream 0 — the layer table

A flat sequence of per-frame records, one record per animation frame, read until the
stream is exhausted:

```
per frame:
    uint8  num_layers        number of layers in this frame
    uint8  flag              unconfirmed (see below)
    num_layers x 6-byte layer descriptor:
        byte[0]  HIDDEN       nonzero => layer hidden (skip it)  <-- CONFIRMED
        byte[1]  OPACITY      0..255                             <-- CONFIRMED
        byte[2]              unknown (usually 0x00, not always)
        byte[3..5]           near-constant, typically B4 64 64; unknown / reserved
```

Cross-checks that all passed on the full sample:

* number of frame records **== the artwork's declared frame count**;
* `sum(num_layers)` over all frames **== K**, the number of bitmaps in stream 1;
* the parse consumes stream 0 **exactly** (no leftover bytes).

**`flag` byte** takes values 0..8 in the sample and is not yet pinned down; it correlates
loosely with layer count / a selected index, so it is most likely the editor's
**active-layer index** for that frame. Not needed for decoding.

**Descriptor byte [0] = hidden flag** (CONFIRMED): nonzero means the layer is hidden in
the editor and must be **excluded** from the composite. Only 7 of 1814 layers in the
sample are hidden (`0x01`), all in pair-01 (4) and pair-03 (3). Skipping them makes both
pairs reconstruct exactly and regresses nothing (every other file has zero hidden
layers). This was found because pair-01's first frame showed extra pixels that were
absent from the rendered artwork.

**Descriptor byte [1] = opacity** is confirmed empirically (see §5): using it as an
alpha value is what makes multi-layer frames reconstruct. Values observed: 0, 6, 26, 28,
… 227, 233, 255. `0` = fully transparent layer; `255` = fully opaque.

The remaining descriptor bytes vary only slightly across the whole sample
(`byte[3:6]` ∈ {b46464, 4f6464, b46483, b46475, 646464}); their meaning is still open
(candidates: layer id, blend mode, name/thumbnail hash). They do **not** affect the
composite in any case we tested.

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
* Layers are painted **bottom → top** over a black canvas.
* Each layer is **alpha-blended** with `alpha = opacity / 255`:

```
for each layer L (bottom -> top) with opacity op:
    a = op / 255
    for each pixel p where L[p] != (0,0,0):     # non-black = painted
        canvas[p] = round( L[p]*a + canvas[p]*(1-a) )
```

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

## 6. Tooling

The finalized decoders built from these findings:

* `servoom.LayerFileDecoder` / `servoom.LayerBean` (Python package) — decode a layer file
  and export a composited WebP (`save_to_webp`) or a layered PSD (`save_to_psd`).
* `docs/src/lib/layerFile.ts` — the same decode + PSD export in the browser (used by the
  web app at servoom.pages.dev).
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

1. Descriptor bytes [2] and [3:6] and the record `flag` byte — semantics unknown.
   (byte[0]=hidden and byte[1]=opacity are confirmed.) Capture files where these vary
   (change one layer's blend mode / name / order in the app and diff) to pin them down.
2. Ground-truth colours: validate pair-09/19 against an actual app/web render rather than
   the format-9 artwork decoder.
3. Frame duration/speed: **not** present in the layer file (header speed bytes are 0);
   it lives in the artwork file. The layer decoder defaults to 100 ms/frame.
4. Non-square canvases: unverified (all Divoom sizes in this sample are square); the
   `sqrt` size recovery assumes square.
