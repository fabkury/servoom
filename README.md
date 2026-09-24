# servoom

### Web user interface at: https://servoom.pages.dev/

### Desktop user interface in https://github.com/tidyhf/Pixoo64-Advanced-Tools

Toolkit for exploring the Divoom Cloud:
 - fetch account data,
 - fetch arts, likes, comments, 
 - download Divoom animations and transcode them into lossless WebP or GIF files.

## Repository layout

The repository hosts three independent "verticals" plus a shared reference corpus:

| Directory  | What                                                                              |
|------------|-----------------------------------------------------------------------------------|
| `python/`  | the `servoom` Python library and CLI (cloud client + decoders), tests, layer tools |
| `docs/`    | the browser app deployed at https://servoom.pages.dev/ (runs the Python decoders via Pyodide) |
| `c/`       | the same library in C99: all decoders + cloud client, see [`c/README.md`](c/README.md) |
| `corpus/`  | tooling for the shared reference corpus (local-only: the artworks belong to Divoom users and are not published), see [`corpus/README.md`](corpus/README.md) |

## Overview

`servoom` wraps the Divoom API so you can archive uploads, metadata, and turn undocumented "pixel bean" files into standard image formats such as GIF or lossless WebP.

The project offers a CLI workflow, decoding utilities that understand the formats observed in the Divoom ecosystem, plus helpers for exporting metadata (likes, comments, others) to CSV.

## Web app / GitHub Pages

A browser-based companion lives in `docs/` and is continuously deployed to Cloudflare R2: https://servoom.pages.dev/. The site mirrors a subset of the Python tooling. Log in with your credentials, browse categories or users, decode previews, and export WebP/GIF/DAT bundles straight from the browser. To work on it locally, `cd docs && npm install && npm run dev`. Comments and likes are not available on the web interface. Use https://github.com/tidyhf/Pixoo64-Advanced-Tools for a desktop browser of comments and likes.

The site runs the **same** decoder in the browser via Pyodide. `python/servoom/pixel_bean.py` and
`python/servoom/pixel_bean_decoder.py` are the single source of truth; `docs/scripts/sync-python.mjs`
copies them into `docs/src/python/` (committed, auto-generated). The copy runs automatically
on `npm run dev`/`npm run build`, and CI fails if the committed copies drift.

## Features
- Authenticate against the Divoom cloud API.
- Fetch uploads, likes, tag metadata, and feeds via `DivoomClient`.
- Download animation binaries and convert them to WebP/GIF or PIL images through `PixelBeanDecoder`, covering Divoom formats 8, 9, 12, 17, 18, 26, 31, 41, 42, and 43 (see [`FILE_FORMATS.md`](FILE_FORMATS.md) for which containers hold stills, animations, or both, with the evidence).
- Decode Divoom **layer files** (format 0x27) into their component layers via `LayerFileDecoder`, and export them to an animated WebP or a **layered PSD** (openable in GIMP/Photoshop with per-layer opacity, visibility and per-frame groups).
- A small CLI (`python -m servoom`) for decoding and downloading, and a `pytest` suite that regression-tests the decoders (synthetic files, plus a local reference corpus when present).

## Requirements
- Python 3.10 or newer (tested on CPython).
- Packages: `requests`, `numpy`, `pillow`, `lzallright`, `pycryptodome`, `zstandard`.
- Optional: `pytoshop` — only needed for exporting layer files to PSD (`LayerBean.save_to_psd`).

## Installation

Install the package dependencies (including the optional `pytoshop` for PSD export):
```powershell
pip install -r python/requirements.txt
```

Or install them explicitly:
```powershell
pip install requests numpy pillow lzallright pycryptodome zstandard
# optional, for PSD export of layer files:
pip install pytoshop
```

## Configure Credentials

Credentials are only needed for the cloud/download features (decoding local files needs
none). Provide the email tied to your Divoom account and the **MD5 hash** of your password
(never the plain password). Resolution order:

1. environment variables `SERVOOM_EMAIL` / `SERVOOM_MD5_PASSWORD`, or
2. a git-ignored `credentials.py`:

```python
# credentials.py
CONFIG_EMAIL = "you@example.com"
CONFIG_MD5_PASSWORD = "md5-hash-of-your-password"
```

Generate the MD5 hash using any online  tool, or locally using Python:

```bash
pip install hashlib

python - <<'PY'
import hashlib
print(hashlib.md5("your-plain-text-password".encode()).hexdigest())
PY
```

Keep your `credentials.py` out of the Internet.

## How to use

The CLI (`python -m servoom --help`, run from the `python/` directory) covers the common flows:

```powershell
cd python
# Decode a local .dat (or a whole folder) to WebP (or GIF with -f gif)
python -m servoom decode downloads/4130000_example.dat -o out
python -m servoom decode downloads/ -o out

# Decode a 0x27 layer file to WebP (+ layered PSD with --psd)
python -m servoom decode-layer downloads/12345_layer.dat -o out --psd

# Download + decode by gallery id, or every upload of a user (needs credentials)
python -m servoom download GALLERY_ID -o downloads
python -m servoom download-user USER_ID -o downloads
```

Outputs land in `downloads/` (raw `.dat`) and `out/` (decoded `.webp`/`.gif`).

### Minimal decoding example

Decode a single `.dat` file into WebP from Python:

```python
from servoom.pixel_bean_decoder import PixelBeanDecoder

bean = PixelBeanDecoder.decode_file("downloads/1234567_example.dat")
bean.save_to_webp("out/example.webp")
```

### Layer files (decode and export to PSD)

Divoom "layer files" (referenced by `LayerFileId` in gallery metadata) are the editable,
layered source for an artwork. Decode one and export it to a layered PSD for GIMP/Photoshop
— each animation frame becomes a layer group, with per-layer opacity and visibility (the
"hide" flag) preserved and black treated as transparent. Since black is the chroma key,
every frame group also carries an opaque black background layer (`fNNN_bg`) at its bottom,
so pixels left transparent in all layers render black exactly as the Divoom app shows them:

```python
from servoom.layer_file_decoder import LayerFileDecoder

layer = LayerFileDecoder.decode_file("downloads/1234567_layer.dat")
layer.save_to_psd("out/example.psd")   # needs: pip install pytoshop
layer.save_to_webp("out/example.webp") # composited animation
```

Command-line tools and the full format write-up live in [`python/layer-tools/`](python/layer-tools/):
`divoom_layer_decoder.py` (self-contained decoder), `layers_to_psd.py` (layer → PSD), and
`LAYER_FILE_FORMAT.md` (the reverse-engineered 0x27 container spec).

### Tests

The `pytest` suite exercises every decoder with synthetic files and, when the local
reference corpus is present (see `corpus/README.md`), re-checks every real artwork against
the recorded baseline:

```powershell
cd python
python -m pytest tests
```

## Repository Guide
- `python/servoom/client.py` – high-level API client (auth, fetch, search, download).
- `python/servoom/http.py` – HTTP transport + the single pagination loop.
- `python/servoom/pixel_bean_decoder.py` – decoders for each known `.dat` container (also the
  canonical source for the web decoder — see below).
- `python/servoom/layer_file_decoder.py` – the 0x27 layer-file decoder and `LayerBean`.
- `python/servoom/cli.py` – the `python -m servoom` command-line interface.
- `python/servoom/gallery_reference.py` – preserved reverse-engineering notes (gallery enums,
  record mappers, experimental endpoints); not wired into live code.
- `corpus/` – tooling for the local-only reference corpus shared by the Python and C test suites.
- `c/` – the C library, CLI and tests (own README).

## Troubleshooting
- **`ImportError: No module named lzallright`** – install the `lzallright` package from PyPI (Windows wheels are available).
- **`Format X unsupported`** – the decoder covers observed formats; contribute samples if you run into a new one.
- **Rate limits or empty payloads** – the Divoom API occasionally throttles; run the CLI with `-v` to inspect the flow and retry with a smaller `Settings(batch_size=...)`.

## Credits
`servoom` expands upon https://github.com/redphx/apixoo by redphx. Without redphx's seminal work, very likely this project would not be here now.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). The decoders build on reverse-engineering work
from https://github.com/redphx/apixoo (MIT).
