# servoom refactor

Reorganize `servoom/` to be **simpler, more straightforward, and production-grade**
without changing observable behavior. This document is the plan of record; check the
boxes as phases land.

## Goals

- Kill duplication (the same loop / same frame-builder written 3–7×).
- One HTTP path, one pagination loop, real logging instead of 200 `print()`s.
- `import servoom` must work with **no credentials and no network** (offline decode is a
  first-class use case).
- Keep the public API stable so `docs/` (the live web tool) and `layer-tools/` keep working.
- Preserve — not delete — the reverse-engineering research currently parked as dead code.

## Decisions (from the owner)

1. **Web Python delivery — "commit generated copies."** `servoom/` is the single source of
   truth. A Node-only script (`docs/scripts/sync-python.mjs`) copies the decode/export
   modules into `docs/src/python/` as **committed, auto-generated** files. A `predev`/
   `prebuild` npm hook regenerates them, and a CI job fails on drift
   (`git diff --exit-code`). Cloudflare / GitHub Pages keep building with plain
   `npm run build` — no Python at build time.
2. **GIF export — "promote into servoom."** `save_to_gif()` (and file-like output support
   for `save_to_webp`) move into `servoom/pixel_bean.py`, so library, CLI, and web share
   one implementation.

## Why a flat layout (not deep `api/ codecs/ models/` packages)

The web loads `pixel_bean.py` + `pixel_bean_decoder.py` as **flat** modules into Pyodide's
FS. Deep subpackages would force the Pyodide loader (and the sync script) to reconstruct a
package tree. For a ~10-module package a flat layout is also just *simpler*, which is the
point. So: split the mega-files, keep the tree flat, and do all decoder de-duplication
**inside** the two web-facing files.

## Target layout

```
servoom/
  __init__.py            public API (unchanged names; new names added, none removed)
  pixel_bean.py          model + webp/gif export (file-like aware)   ← web-canonical
  pixel_bean_decoder.py  format registry + decoders (deduped in-file) ← web-canonical
  layer_file_decoder.py  0x27 layer decoder + LayerBean (logging-ized)
  http.py                DivoomSession (headers/timeout/retries/ReturnCode) + paginate()
  client.py              DivoomClient: auth + thin fetch/download/decode over http.py
  csv_export.py          export_artworks_to_csv + FIELD_MAPPINGS (off the client)
  config.py              Settings: timeouts/batch/retries/headers — NO creds, NO DEBUG_MODE
  credentials.py         load_credentials(): env first, optional credentials.py fallback
  const.py               ApiEndpoint + Server (only the parts actually used)
  gallery_reference.py   PRESERVED research: gallery enums, *Info dict-mappers,
                         experimental endpoint catalog (kept, documented, not wired in)
  logging.py             get_logger()/configure — replaces print()
  cli.py                 real CLI (`python -m servoom ...`) — what the README already promises
tests/                   pytest: decode every reference asset, assert frames/dims/hash
docs/scripts/sync-python.mjs   generate docs/src/python/*.py from servoom/ (Node only)
```

## Validation strategy

- **Golden baseline:** `tests/` decodes every `reference-animations/**/*.dat` and asserts
  frame count, dimensions, and a content hash captured *before* the refactor. Format 26
  (128×128 hierarchical) is the most complex decoder and is fully covered.
- **Web parity:** after regenerating `docs/src/python/`, run the *same* baseline through the
  generated flat modules in CPython (the real `lzallright`/`zstandard`/`pycryptodome` are
  installed) and assert byte-identical output to `servoom/`. Then `npm run build` to prove
  the `?raw` imports and TS still compile.

## Research preservation

`const.py`'s gallery enums (`GalleryCategory/Type/Sorting/Dimension`), the
`BaseDictInfo`/`AlbumInfo`/`UserInfo`/`GalleryInfo` mappers, and `config.py`'s commented-out
experimental endpoint URLs are **reverse-engineering findings**, not live code. They move to
`servoom/gallery_reference.py` with a header explaining provenance and status, so they stay
discoverable and importable for future work instead of rotting as dead code.

## Phases (each independently shippable & behavior-preserving)

- [x] 0. Test safety net: `tests/test_reference_decode.py` from the golden baseline.
- [x] 1. Preserve research: `const.py` → keep `ApiEndpoint`/`Server`; move the rest to
      `gallery_reference.py`.
- [x] 2. Fix import-time crash: `credentials.py` (lazy, env-first); drop the module-level
      `from credentials import …` in `config.py`.
- [x] 3. `logging.py`; replace `print()` in library paths.
- [x] 4. Decoder de-dup (in `pixel_bean_decoder.py`): one `_frames_from_rgb`, shared 0x0C,
      one embedded-image compositor, registry dispatch, `@staticmethod`, dual import.
- [x] 5. Promote `save_to_gif` + file-like `save_to_webp` into `servoom/pixel_bean.py`.
- [x] 6. `docs/scripts/sync-python.mjs` + npm hooks + CI drift check; regenerate committed
      `docs/src/python/*.py`; prove web parity.
- [x] 7. `http.py` (session + `paginate`); slim `client.py` onto it; drop scratch
      (`debug_fetch`, hardcoded report payloads) into `gallery_reference.py`.
- [x] 8. `csv_export.py`: move CSV out of the client.
- [x] 9. `config.py` trim (no `DEBUG_MODE` global); `cli.py`; fix `README.md`.

## Results

Validation (all green):

- `python -m pytest tests` → **16 passed** (12 reference assets byte-identical + 3 synthetic
  format tests + 1 coverage guard).
- Web parity: the generated `docs/src/python/*.py`, run flat in CPython, decode all 12
  reference files to **byte-identical** output and support `BytesIO` `save_to_webp`/
  `save_to_gif` (the browser bridge path).
- `cd docs && npm run build` succeeds (prebuild sync runs, tsc + vite compile).
- `import servoom` works with no credentials and no network; `DivoomClient()` with no
  credentials raises a clean `CredentialsError` instead of crashing at import.

Size (lines):

| module | before | after |
| --- | --- | --- |
| `client.py` | 1495 | 274 |
| `pixel_bean_decoder.py` | 1666 | 1408 (−~260 of copy-paste; palette engine preserved verbatim) |
| `config.py` (god-class) | 120 | split into `config` 37 + `credentials` 67 + `csv_export` 128 + `http` 127 + `util` 39 + `logging` 31 |
| `const.py` | 159 | 29 (rest preserved in `gallery_reference.py` 186) |

Notable behavior changes (intentional, documented):

- The silent global `DEBUG_MODE`/`DEBUG_LIMIT=1000` cap on every fetch is gone; callers pass
  an explicit `limit`.
- Fetches now retry transient network errors uniformly (previously only `fetch_likes`).
- Library code logs instead of `print()`ing (silent by default via a `NullHandler`).
- `debug_fetch` and the hardcoded `fetch_report_gallery` scratch were removed; the endpoint
  knowledge they encoded is preserved in `gallery_reference.py`.
- pandas/tqdm dropped (CSV now uses stdlib `csv`).

## Public API compatibility

`servoom/__init__.py` keeps exporting `PixelBean`, `PixelBeanState`, `PixelBeanDecoder`,
`LayerFileDecoder`, `LayerBean`, `DivoomClient`. `layers_to_psd.py` imports
`from servoom import LayerFileDecoder` — unaffected. The web bridge calls
`PixelBeanDecoder.decode_stream`, `bean.frames_data/total_frames/speed/row_count/
column_count`, `save_to_webp`, `save_to_gif` — all preserved.
