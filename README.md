# servoom

### Web user interface at: https://servoom.pages.dev/

### Desktop user interface in https://github.com/tidyhf/Pixoo64-Advanced-Tools

Toolkit for exploring the Divoom Cloud:
 - fetch account data,
 - fetch arts, likes, comments, 
 - download Divoom animations and transcode them into lossless WebP or GIF files.

## Overview

`servoom` wraps the Divoom API so you can archive uploads, metadata, and turn undocumented "pixel bean" files into standard image formats such as GIF or lossless WebP.

The project offers a CLI workflow, decoding utilities that understand the formats observed in the Divoom ecosystem, plus helpers for exporting metadata (likes, comments, others) to CSV.

## Web app / GitHub Pages

A browser-based companion lives in `docs/` and is continuously deployed to Cloudflare R2: https://servoom.pages.dev/. The site mirrors a subset of the Python tooling. Log in with your credentials, browse categories or users, decode previews, and export WebP/GIF/DAT bundles straight from the browser. To work on it locally, `cd docs && npm install && npm run dev`. Comments and likes are not available on the web interface. Use https://github.com/tidyhf/Pixoo64-Advanced-Tools for a desktop browser of comments and likes.

The site runs the **same** decoder in the browser via Pyodide. `servoom/pixel_bean.py` and
`servoom/pixel_bean_decoder.py` are the single source of truth; `docs/scripts/sync-python.mjs`
copies them into `docs/src/python/` (committed, auto-generated). The copy runs automatically
on `npm run dev`/`npm run build`, and CI fails if the committed copies drift.

## Features
- Authenticate against the Divoom cloud API.
- Fetch uploads, likes, tag metadata, and feeds via `DivoomClient`.
- Download animation binaries and convert them to WebP/GIF or PIL images through `PixelBeanDecoder`, covering Divoom formats 9, 17, 18, 26, 31, 41, 42, and 43.
- Decode Divoom **layer files** (format 0x27) into their component layers via `LayerFileDecoder`, and export them to an animated WebP or a **layered PSD** (openable in GIMP/Photoshop with per-layer opacity, visibility and per-frame groups).
- A small CLI (`python -m servoom`) for decoding and downloading, and a `pytest` suite that regression-tests the decoders against bundled reference assets.
- Reference assets and comparison scripts for regression-testing new decoder logic.

## Requirements
- Python 3.10 or newer (tested on CPython).
- Packages: `requests`, `numpy`, `pillow`, `lzallright`, `pycryptodome`, `zstandard`.
- Optional: `pytoshop` — only needed for exporting layer files to PSD (`LayerBean.save_to_psd`).

## Installation

Install the package dependencies (including the optional `pytoshop` for PSD export):
```powershell
pip install -r requirements.txt
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

The CLI (`python -m servoom --help`) covers the common flows:

```powershell
# Decode a local .dat (or a whole folder) to WebP (or GIF with -f gif)
python -m servoom decode downloads/4130000_example.dat -o out
python -m servoom decode downloads/ -o out

# Decode a 0x27 layer file to WebP (+ layered PSD with --psd)
python -m servoom decode-layer downloads/12345_layer.dat -o out --psd

# Download + decode by gallery id, or every upload of a user (needs credentials)
python -m servoom download 4152005 -o downloads
python -m servoom download-user 401670591 -o downloads
```

Outputs land in `downloads/` (raw `.dat`) and `out/` (decoded `.webp`/`.gif`).

### Minimal decoding example

Decode a single `.dat` file into WebP from Python:

```python
from servoom.pixel_bean_decoder import PixelBeanDecoder

bean = PixelBeanDecoder.decode_file("downloads/401553003/4130000_example.dat")
bean.save_to_webp("out/example.webp")
```

### Layer files (decode and export to PSD)

Divoom "layer files" (referenced by `LayerFileId` in gallery metadata) are the editable,
layered source for an artwork. Decode one and export it to a layered PSD for GIMP/Photoshop
— each animation frame becomes a layer group, with per-layer opacity and visibility (the
"hide" flag) preserved and black treated as transparent:

```python
from servoom.layer_file_decoder import LayerFileDecoder

layer = LayerFileDecoder.decode_file("downloads/12345_layer.dat")
layer.save_to_psd("out/example.psd")   # needs: pip install pytoshop
layer.save_to_webp("out/example.webp") # composited animation
```

Command-line tools and the full format write-up live in [`layer-tools/`](layer-tools/):
`divoom_layer_decoder.py` (self-contained decoder), `layers_to_psd.py` (layer → PSD), and
`LAYER_FILE_FORMAT.md` (the reverse-engineered 0x27 container spec).

### Tests

The `pytest` suite decodes every bundled reference asset and asserts the output is
byte-for-byte unchanged (plus synthetic files for formats the samples don't cover):

```powershell
python -m pytest tests
# or the equivalent launcher:
python run_tests.py
```

## Repository Guide
- `servoom/client.py` – high-level API client (auth, fetch, search, download).
- `servoom/http.py` – HTTP transport + the single pagination loop.
- `servoom/pixel_bean_decoder.py` – decoders for each known `.dat` container (also the
  canonical source for the web decoder — see below).
- `servoom/layer_file_decoder.py` – the 0x27 layer-file decoder and `LayerBean`.
- `servoom/cli.py` – the `python -m servoom` command-line interface.
- `servoom/gallery_reference.py` – preserved reverse-engineering notes (gallery enums,
  record mappers, experimental endpoints); not wired into live code.
- `reference-animations/` – sample binary assets used by the tests.
- `REFACTOR.md` – the structure/rationale for the current layout.

## Troubleshooting
- **`ImportError: No module named lzallright`** – install the `lzallright` package from PyPI (Windows wheels are available).
- **`Format X unsupported`** – the decoder covers observed formats; contribute samples if you run into a new one.
- **Rate limits or empty payloads** – the Divoom API occasionally throttles; run the CLI with `-v` to inspect the flow and retry with a smaller `Settings(batch_size=...)`.

## Credits
`servoom` expands upon https://github.com/redphx/apixoo by redphx. Without redphx's seminal work, very likely this project would not be here now.
