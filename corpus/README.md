# Reference corpus

The shared test oracle for every servoom vertical: a few hundred real Divoom artworks and
layer files covering every container format the decoders support, together with what the
**Python** decoders produce for each of them. The C library (`c/tests/test_corpus.c`) is
tested for byte-identical output against it.

The corpus is **local-only**. The artworks belong to Divoom users, so neither the payloads
nor the manifest that lists them (gallery ids, cloud file ids, titles, author ids) is
published; only the tooling is tracked. Everything below is git-ignored except `corpus.py`:

| File            | Tracked | Contents                                                      |
|-----------------|---------|---------------------------------------------------------------|
| `manifest.json` | no      | every file: gallery id, cloud file id, format byte, size, SHA-256 |
| `baseline.json` | no      | per file: frames, canvas, speed, SHA-256 of all decoded RGB bytes (layer files also hash the layer table and raw bitmaps) |
| `files/`        | no      | the payloads, as `files/fmtNN/<galleryid>.dat` or `files/layerNN/<galleryid>.dat` |
| `corpus.py`     | yes     | the tool that builds, fetches, verifies and baselines the corpus |

Without a local corpus the C and Python corpus tests are skipped; the synthetic tests
still cover every format. To build your own corpus, see "Extending the corpus".

Current contents: 1997 files (376 MB) -- 40 x format 8, 322 x 9, 40 x 12, 86 x 17, 185 x 18, 587 x 26,
147 x 31, 14 x 41, 398 x 42, 98 x 43, 40 x layer 0x27, 40 x layer 0x28 (most were added by
the 2026-09-24 still-vs-animation survey, see `FILE_FORMATS.md`). Baseline: 0 oracle errors.

## Getting the payloads (if you have a manifest)

Set Divoom credentials (`SERVOOM_EMAIL` + `SERVOOM_PASSWORD`, or `SERVOOM_MD5_PASSWORD`,
or a git-ignored `python/credentials.py`) and run:

```powershell
pip install -r python/requirements.txt
python corpus/corpus.py fetch     # downloads every manifest entry, verifies SHA-256
python corpus/corpus.py verify    # checks what is on disk against the manifest
python corpus/corpus.py stats     # per-format histogram
```

Artworks deleted from the cloud since the manifest was written will fail to fetch; the
rest of the corpus is still usable (the C test reports missing files separately).

## Extending the corpus

```powershell
# scan gallery feeds and keep files until each format has N samples
python corpus/corpus.py discover --default-target 40 --target 0x29=20
# add local <galleryid>_<name>.dat files (e.g. an earlier bulk download)
python corpus/corpus.py import-dir path/to/downloads
# decode the new entries with the Python decoders and extend baseline.json
python corpus/corpus.py baseline
```

`discover` pages through category feeds (`GetCategoryFileListV2`) across canvas sizes and
gallery types, downloads each artwork (and its layer file when the record has a
`LayerFileId`) and keeps it only if its format byte is still under target. The server's
`FileType` classes (`--type pic anim multi_pic multi_anim`) map onto container formats
as documented in [`FILE_FORMATS.md`](../FILE_FORMATS.md); `pic` only exists at 16px
(format 8) and `multi_pic` only from 32px up, so a stratified run needs all four. `baseline`
decodes with `PixelBeanDecoder` / `LayerFileDecoder`; when the Python decoder itself
fails on a file the baseline records the error so the C decoder is required to fail on it
too. After changing a Python decoder deliberately, run `baseline --rebuild`.

`python corpus/corpus.py dump FILE` writes a file's decoded frames as `.rgb` and `.ppm`
for eyeballing or diffing against the C CLI's `servoom decode`.
