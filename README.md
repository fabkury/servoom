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

## Features
- Authenticate against the Divoom cloud API.
- Fetch uploads, likes, tag metadata, and feeds via `DivoomClient`.
- Download animation binaries and convert them to WebP or PIL images through `PixelBeanDecoder`, covering Divoom formats 9, 17, 18, 26, 31, 42, and 43.
- Batch pipelines that export CSV snapshots (`servoom.cli`) and sample smoke tests (`run_tests.py`).
- Reference assets and comparison scripts for regression-testing new decoder logic.

## Requirements
- Python 3.10 or newer (tested on CPython).
- Packages: `requests`, `numpy`, `pillow`, `pandas`, `tqdm`, `lzallright`, `pycryptodome`, `zstandard`.

## Installation

Just install the package dependencies:
```powershell
pip install requests numpy pillow pandas tqdm lzallright pycryptodome zstandard
```

## Configure Credentials

The tooling reads **hashed** credentials from `credentials.py`. Fill in the email tied to your Divoom account and the MD5 hash of your password (not your password itself!):

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

Once dependencies and credentials are in place, run the bundled CLI. It will sign in, fetch a curated gallery (by default category 18, "Recommended"), download the binaries into `.dat` files (the file extension doesn't mean anything), and transcode them to WebP:

```powershell
python -m servoom.cli
```

Outputs land in `downloads/` (raw `.dat`) and `out/` (decoded `.webp`). Tweak the helpers inside `servoom/cli.py` to point at different user IDs, categories, or export targets.

### Minimal decoding example

Decode a single `.dat` file into WebP without touching the CLI:

```python
from servoom.pixel_bean_decoder import PixelBeanDecoder

bean = PixelBeanDecoder.decode_file("downloads/401553003/4130000_example.dat")
bean.save_to_webp("out/example.webp")
```

### Smoke test

The repository includes a tiny regression script that exercises the decoder against the bundled reference assets:

```powershell
python run_tests.py
```

## Repository Guide
- `servoom/client.py` – high-level API client with fetch, search, and download utilities.
- `servoom/pixel_bean_decoder.py` – low-level decoders for each known `.dat` container.
- `servoom/cli.py` – orchestrated workflows for exporting CSVs, downloading content, and decoding assets.
- `reference-animations/` – sample binary assets plus expected outputs for regression checks.

## Troubleshooting
- **`ImportError: No module named lzallright`** – install the `lzallright` package from PyPI (Windows wheels are available).  
- **`Format X unsupported`** – the decoder covers observed formats; contribute samples if you run into a new one.  
- **Rate limits or empty payloads** – the Divoom API occasionally throttles; enable debug flags in `servoom/cli.py` to inspect payloads and retry with smaller `Config.BATCH_SIZE`.

## Credits
`servoom` expands upon https://github.com/redphx/apixoo by redphx. Without redphx's seminal work, very likely this project would not be here now.
