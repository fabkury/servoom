# Divoom artwork containers: which ones are stills, which are animations

Every artwork downloaded from the Divoom cloud is a `.dat` file whose first byte is a
container format id. This page records what each container actually holds in the wild
(one frame, many frames, or either), based on files pulled from the live gallery feeds on
2026-09-24 and decoded with the servoom decoders. It supersedes the folklore in the older
decoder comments ("single animation", "multiple picture format", ...), which was partly
wrong.

## Summary

| Format | Verdict | What the samples show |
|-------:|---------|-----------------------|
| 8 (0x08)  | **still only** | 16x16, exactly one frame, no header at all. Unknown to servoom until this survey. |
| 9 (0x09)  | animation container, **can hold a still** | 16x16, 1 to 60 frames; about 7% are 1-frame files. |
| 17 (0x11) | **still only** | 32x32 (two 64x64 seen), exactly one frame; the container has no frame count. |
| 18 (0x12) | animation container, **can hold a still** | 32x32 (and 16-pixel-tall multi-panel strips), 1 to 60 frames; about 2% are 1-frame files. |
| 26 (0x1A) | **both**, in roughly equal numbers | 64x64 and 128x128; every still at these sizes is a 1-frame format-26 file. |
| 31 (0x1F) | **animation only** (in the wild) | 128x128, never fewer than 38 frames in 147 samples, only ever listed as an animation. |
| 41 (0x29) | **both**; mostly stills | 256x256; 14 samples from a single uploader, 10 of them 1-frame. |
| 42 (0x2A) | **both**, in roughly equal numbers | 256x256; every still at this size is a 1-frame format-42 file. |
| 43 (0x2B) | **animation only** (in the wild) | 256x256, never fewer than 20 frames in 98 samples, only ever listed as an animation. |
| 12 (0x0C) | scrolling banner (neither) | 16x16 device content: four 16x16 tiles forming a 64x16 strip the device scrolls; decoded as a 64-frame marquee. |

"Still" here means the decoded container holds exactly one frame. Only two multi-frame
files in the survey had all their frames identical (one format 9, one format 42), so the
two possible definitions agree in practice.

Nothing in formats 9, 18, 26, 41 and 42 marks a file as a still: a still is simply a file
whose frame-count byte is 1. A consumer that wants to tell stills from animations has to
read the frame count (or trust the server's `FileType`, next section); the format byte
alone is not enough for those five containers. Formats 8 and 17 are stills by construction
(there is no frame count to read), and formats 31 and 43 were never observed as stills.

## The server's own classification

Gallery listings (`GetCategoryFileListV2` and friends) take and return a `FileType`
field. The values that exist in the feeds depend on the canvas size:

| `FileType` | Name | Canvas sizes where it occurs | Container format of every sample |
|-----------:|------|------------------------------|----------------------------------|
| 0 | picture | 16x16 only | 8 |
| 1 | animation | 16x16 only | 9 |
| 2 | multi-picture | 32, 64, 128, 256 | 17 (32/64px), 26 (64/128px), 42 (256px) |
| 3 | multi-animation | 16 (rare), 32, 64, 128, 256 | 18 (16/32px), 26 (64/128px), 31 (128px), 41 (256px), 42 (256px), 43 (256px) |
| 8 | banner (not exposed by the gallery filters) | 16x16 | 12 |

"Multi" is Divoom's word for the tiled canvases larger than a single 16x16 panel, not for
multiple frames. The 16x16 `FileType=3` files are format 18 strips of several 16x16
panels (1x2, 2x1, 1x4, 4x1 tiles were seen), i.e. content for chained Pixoo-16 devices.

Cross-checking the server's label against the decoded frame count:

| `FileType` | Files | 1 frame | >1 frames |
|-----------:|------:|--------:|----------:|
| 0 picture | 150 | 150 | 0 |
| 1 animation | 300 | 28 | 272 |
| 2 multi-picture | 597 | 597 | 0 |
| 3 multi-animation | 1953 | 147 | 1806 |

So the picture classes are exact (a picture is always one frame), but the animation
classes are not: about 8% of the files the server lists as animations decode to a single
frame. Those are animation containers (9, 18, 26, 41, 42) that the uploading app filled
with one frame; the server keeps the client's choice rather than inspecting the file.

## Per-format evidence

Files were fetched from the live cloud on 2026-09-24 in three passes: paging the
category feeds (new, recommended, top, character, nature, creative, photo, animal,
person, food) for every combination of canvas size (16/32/64/128/256) and `FileType`
(0/1/2/3); then the complete recent upload lists (120 each) of the 17 users found to
produce formats 31 and 43; plus the files that were already in the local reference corpus.
Each file was decoded with `PixelBeanDecoder` and the number of frames it produced was
recorded. 3199 artworks in total.

| Format | Files | 1 frame | >1 frames | Frames (min–max) | Canvas | Server `FileType` of the samples |
|-------:|------:|--------:|----------:|------------------:|--------|----------------------------------|
| 8 (0x08) | 150 | 150 | 0 | 1–1 | 16x16 (150) | picture 150 |
| 9 (0x09) | 414 | 29 | 385 | 1–60 | 16x16 (414) | animation 300, not recorded 114 |
| 17 (0x11) | 106 | 106 | 0 | 1–1 | 32x32 (104), 64x64 (2) | multi-picture 106 |
| 18 (0x12) | 244 | 5 | 239 | 1–60 | 32x32 (233), 32x16 (6), 16x64 (2), 16x32 (2), 64x16 (1) | multi-animation 238, not recorded 6 |
| 26 (0x1A) | 1227 | 417 | 810 | 1–92 | 128x128 (796), 64x64 (431) | multi-animation 853, multi-picture 314, not recorded 60 |
| 31 (0x1F) | 147 | 0 | 147 | 38–92 | 128x128 (147) | multi-animation 147 |
| 41 (0x29) | 14 | 10 | 4 | 1–90 | 256x256 (14) | multi-animation 14 |
| 42 (0x2A) | 793 | 258 | 535 | 1–92 | 256x256 (793) | multi-animation 603, multi-picture 177, not recorded 13 |
| 43 (0x2B) | 98 | 0 | 98 | 20–92 | 256x256 (98) | multi-animation 98 |

("Not recorded" = files from the pre-existing corpus whose listing metadata was not kept.)

### Format 8: the missing still format

Every 16x16 file listed as a picture (`FileType=0`) is format 8, a container servoom did
not know: `[0x08]` followed by the AES-CBC ciphertext of exactly one raw 16x16 RGB frame
(768 bytes), so every file is 769 bytes long. It is format 9 without format 9's speed
prefix. All 150 samples decode to one frame; there is nowhere in the file for a second
one. Decoders for it were added to the Python and C libraries (`PicSingleDecoder`,
`sv_decode_fmt08`).

### Format 17

The container carries a tile grid and one LZO-compressed frame, and no frame count. All
106 samples are single frames (32x32, plus two 64x64 files from one of the format-43
uploaders). The decoder's fixed `speed = 40` is an invention of the decoder (a still has
no timing), kept for compatibility.

### Formats 9, 18, 26, 42: frame count decides

These carry a frame count (format 9 derives it from the payload length) and are used for
both. For 64x64, 128x128 and 256x256 canvases the app has no dedicated still format:
every "multi-picture" listing at those sizes is a 1-frame format 26 or 42 file
(314 + 177 samples, without exception). The 1-frame files carry a `speed` like any other
(mostly 100 ms).

Format 18 also turned out to hold non-square canvases: 1xN and Nx1 grids of 16x16 tiles
(11 samples, e.g. a 64x16 strip). The tile-placement loop inherited from apixoo wrapped
the tile column at `row_count`, which only works for square grids; it now wraps at
`column_count` (tiles are stored row-major). The C port and its unit test were changed
to match.

### Formats 31 and 43: animation only, as far as the feeds show

Both are rare and come from few uploaders (format 31 from 4 users across the whole
survey, format 43 from 14). They appeared only under `FileType=3` listings; none of the
597 multi-picture files at 128x128 or 256x256 used them. Reading the recent upload
history of those users (1416 files) shows the same clients writing their stills as
1-frame format 9, 17, 18, 26, 41 or 42 files and never as format 31 or 43. The smallest
sample has 20 frames (format 43) and 38 frames (format 31). Both containers have a
frame-count byte, so a 1-frame file is *representable*; it just has not been seen.

### Format 41: rare, found only through one uploader

No format 41 file appeared in any category feed (about 2300 feed downloads here, several
thousand during earlier corpus building), which is why it was believed to be a legacy
format. It surfaced in the upload history of one of the format-43 producers: 14 files,
all 256x256, all listed as multi-animation, 10 of them single frames (`speed` 1000) and
4 real animations (26 to 90 frames). The existing decoder handles all 14 (verified
visually); they are now in the reference corpus.

### Format 12: a scrolling banner

16x16 files under `FileType=8` (a value the gallery filters do not expose, but which
user upload lists return alongside everything else) are format 12 (0x0C):
`[0x0C][mode][speed BE16]` + AES-CBC of exactly four 16x16 RGB tiles (3076 bytes every
time, 46 samples). Decrypted with format 9's layout and laid side by side the four tiles
form a 64x16 picture (text, a plane over clouds, a stock chart) that the device scrolls
across its 16x16 panel. The `mode` byte takes the values 1, 2 and 3 in the samples; its
meaning is unknown and the decoders ignore it (Python keeps it as
`metadata['banner_mode']`). `speed` ranges from 25 to 800 ms.

It is neither a still nor a stored frame animation. servoom decodes it as the marquee a
16x16 device would show: 64 frames of a 16x16 window sliding right-to-left over the strip
one pixel per frame, wrapping around, each frame lasting `speed` ms. The flat strip stays
reachable (`metadata['banner_strip']` in Python, `servoom_pixel_bean_banner_strip()` in
C, shown under the preview in the web tool). The scroll direction, step and wrap-around
are an interpretation of the content, not verified on a device.

## Reproducing

The local reference corpus (`corpus/`, git-ignored payloads) keeps every file registered
by the survey, with the decoded frame count of each in `corpus/baseline.json`, so the
table above can be recomputed offline from the baseline. `python corpus/corpus.py
discover` pages the same feeds; pass `--type pic anim multi_pic multi_anim` to stratify
by the server's classes.
