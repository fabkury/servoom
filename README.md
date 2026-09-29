# servoom

Read the Divoom cloud and decode its pixel art.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](python/)
[![C99](https://img.shields.io/badge/C-C99-blue.svg)](c/)
[![Web app](https://img.shields.io/badge/web%20app-servoom.pages.dev-brightgreen.svg)](https://servoom.pages.dev/)
[![Docs sync](https://github.com/fabkury/servoom/actions/workflows/python-sync-check.yml/badge.svg)](https://github.com/fabkury/servoom/actions/workflows/python-sync-check.yml)
[![Deploy](https://github.com/fabkury/servoom/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/fabkury/servoom/actions/workflows/deploy-pages.yml)

Divoom's pixel-art devices (Pixoo, Ditoo, Times Gate, ...) share a community gallery whose
artworks are stored in undocumented binary containers and served by an undocumented API.
servoom maps that API, read-only, and decodes every container seen in the wild into
standard images. It ships as a Python library and CLI, a C99 library and CLI with
byte-identical output, and a browser app.

## What it does

- **Reads the cloud.** Gallery feeds with the app's own filters, search, user profiles,
  artist rankings, albums, playlists, tags, likes, threaded comments, the official forum
  and the notification inbox. Most of it works without an account.
- **Decodes the files.** Formats 8, 9, 12, 17, 18, 26, 31, 41, 42 and 43 (16 to 256 px,
  stills, animations, multi-panel strips, scrolling banners) to lossless WebP, GIF or raw
  RGB, plus the layered "layer file" source of an artwork to a layered PSD.
- **Documents what it found.** Endpoint maps and container layouts, verified against the
  live service, so the next person does not have to reverse-engineer them again.

Writing to the cloud (likes, comments, uploads) is deliberately out of scope.

## Quick start

```powershell
pip install -r python/requirements.txt
cd python
```

```python
from servoom import DivoomClient
from servoom.const import GalleryCategory, GallerySort

c = DivoomClient(anonymous=True)                       # no account needed for listings
for art in c.fetch_category_files(GalleryCategory.ANIMAL, limit=30,
                                  FileSort=GallerySort.POPULAR):
    print(art["GalleryId"], art["FileName"], art["LikeCnt"])

c = DivoomClient(); c.login()                          # downloads need credentials (python/README.md)
bean, path = c.download_art_by_id(601799, "downloads")
```

```powershell
python -m servoom decode downloads/601799_Blink.dat -o out     # -> out/601799_Blink.webp
python -m servoom decode-layer downloads/1234_layer.dat --psd  # layered PSD for GIMP/Photoshop
```

The full walkthrough (credentials, CLI, API, tests) is in [`python/README.md`](python/README.md).

## Repository

| Directory | Contents |
|-----------|----------|
| [`python/`](python/) | the `servoom` library and CLI: cloud client, decoders, layer tools, tests |
| [`c/`](c/) | the same client and decoders in C99, tested byte-for-byte against the Python output |
| [`docs/`](docs/) | the browser app at [servoom.pages.dev](https://servoom.pages.dev/), running the Python decoders via Pyodide |
| [`corpus/`](corpus/) | tooling for the reference corpus both test suites share (the artworks themselves are local-only) |

Reference documents, all reverse-engineered and verified live:

| Document | Covers |
|----------|--------|
| [`CLOUD_API.md`](CLOUD_API.md) | gallery, user, tag, discovery and playlist endpoints: fields, filters, page caps, which calls need a token |
| [`FORUM_API.md`](FORUM_API.md) | the forum feed, comments, notification inbox and chat-room directory |
| [`FILE_FORMATS.md`](FILE_FORMATS.md) | which container holds stills or animations, with the evidence per format |
| [`python/layer-tools/LAYER_FILE_FORMAT.md`](python/layer-tools/LAYER_FILE_FORMAT.md) | the layer-file container (format 0x27) |

## Other ways in

- **Browser:** [servoom.pages.dev](https://servoom.pages.dev/) browses categories and users and exports WebP, GIF or the raw file. It runs the same decoder as the Python library.
- **C:** `c/` builds a static library and a `servoom` executable with the same commands; see [`c/README.md`](c/README.md).
- **Desktop:** [Pixoo64-Advanced-Tools](https://github.com/tidyhf/Pixoo64-Advanced-Tools) by tidyhf is a third-party desktop browser for comments and likes.

## Contributing

The decoders are held to one contract: byte-identical output between Python and C on the
reference corpus. A decoder change means updating the Python source, regenerating the
corpus baseline, and passing `ctest` in `c/`. Endpoint additions are read-only and go into
the endpoint map first. Never commit credentials or other users' artworks; both are
git-ignored on purpose.

## Credits

servoom expands upon [apixoo](https://github.com/redphx/apixoo) by redphx, whose work on
the Divoom API and file formats made this project possible.

## License

[Apache License 2.0](LICENSE). The decoders build on reverse-engineering work from
[apixoo](https://github.com/redphx/apixoo) (MIT).
