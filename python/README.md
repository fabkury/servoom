# servoom (Python)

The `servoom` library and command-line tool: a read-only client for the Divoom cloud and
decoders for every artwork container seen in the wild. The Python decoders are the
specification the C port and the web app are tested against. Run everything from this
directory. Part of [servoom](../README.md).

## Install

Python 3.10 or newer.

```powershell
pip install -r requirements.txt
```

That installs `requests`, `numpy`, `pillow`, `lzallright`, `pycryptodome`, `zstandard` and
the optional `pytoshop` (only needed to export layer files to PSD).

## Credentials

Decoding local files needs no account, and most cloud listings work anonymously
(`DivoomClient(anonymous=True)`; [`CLOUD_API.md`](../CLOUD_API.md) lists which endpoints
answer without a token). Downloads by gallery id, tag galleries, your own lists and the
inbox need a login. The client takes the email of a Divoom account and the **MD5 hash** of
its password, never the plain password, from one of:

1. the environment: `SERVOOM_EMAIL` and `SERVOOM_MD5_PASSWORD` (or `SERVOOM_PASSWORD`,
   which is hashed for you), or
2. a git-ignored `credentials.py` next to this file:

```python
CONFIG_EMAIL = "you@example.com"
CONFIG_MD5_PASSWORD = "md5-hash-of-your-password"
```

To hash a password locally:

```powershell
python -c "import hashlib, sys; print(hashlib.md5(sys.argv[1].encode()).hexdigest())" "your-password"
```

## Command line

```powershell
python -m servoom --help
python -m servoom decode downloads/4130000_example.dat -o out        # .dat (or a folder) -> WebP
python -m servoom decode downloads/ -o out -f gif                     # ... or GIF
python -m servoom decode-layer downloads/12345_layer.dat -o out --psd # layer file -> WebP + PSD
python -m servoom download GALLERY_ID -o downloads                   # needs credentials
python -m servoom download-user USER_ID -o downloads                 # every upload of a user
```

Raw files land in `downloads/`, decoded images in `out/`. Add `-v` to see the requests.

## Library

### Reading the cloud

```python
from servoom import DivoomClient
from servoom.const import GalleryCategory, GallerySize, GallerySort, ForumRegion

c = DivoomClient(anonymous=True)
arts = c.fetch_category_files(GalleryCategory.NEW, limit=90,
                              FileSort=GallerySort.POPULAR,
                              FileSize=GallerySize.W64 | GallerySize.W128)
experts = c.fetch_experts(limit=30)                  # ranked artists, 5 sample artworks each
albums = c.fetch_albums()                            # curated collections
thread = c.fetch_comments_for_art(601799)            # replies nest in CommentChildList
posts = c.fetch_forum_posts(region=ForumRegion.INTERNATIONAL, limit=20)
profile = c.fetch_someone_info(400803327)
medals = c.fetch_user_medals(400803327)

c = DivoomClient(); c.login()                        # token-only calls
bean, path = c.download_art_by_id(601799, "downloads")
mine = c.fetch_my_arts()
inbox = c.fetch_unread_counts()
```

Every listing pages for you and takes the app's own filters as keyword arguments. The
endpoint map, with fields and page caps, is in [`CLOUD_API.md`](../CLOUD_API.md) and
[`FORUM_API.md`](../FORUM_API.md); `servoom/gallery_reference.py` keeps the older
probing notes.

### Decoding

```python
from servoom.pixel_bean_decoder import PixelBeanDecoder

bean = PixelBeanDecoder.decode_file("downloads/1234567_example.dat")
print(bean.width, bean.height, bean.total_frames, bean.speed)
bean.save_to_webp("out/example.webp")               # lossless, animated
bean.save_to_gif("out/example.gif")
frame = bean.get_frame_image(1)                     # Pillow image
```

Which container holds stills, animations or both is documented in
[`FILE_FORMATS.md`](../FILE_FORMATS.md).

### Layer files

The layered source of an artwork (`LayerFileId` in gallery metadata) decodes to its
component layers. The PSD export keeps one group per frame with per-layer opacity and
visibility; black is the chroma key, so each frame group also carries an opaque black
background layer so that untouched pixels render black, as in the app.

```python
from servoom.layer_file_decoder import LayerFileDecoder

layer = LayerFileDecoder.decode_file("downloads/1234567_layer.dat")
layer.save_to_psd("out/example.psd")     # needs pytoshop
layer.save_to_webp("out/example.webp")   # composited animation
```

Stand-alone tools and the container spec live in [`layer-tools/`](layer-tools/).

## Tests

```powershell
python -m pytest tests
```

Synthetic files cover every decoder and the client is tested offline against recorded
responses. When the local reference corpus is present (see
[`../corpus/README.md`](../corpus/README.md)) every real artwork is re-checked against
the recorded baseline.

## Layout

| File | Role |
|------|------|
| `servoom/client.py` | `DivoomClient`: login, anonymous mode, every read-only call |
| `servoom/const.py` | endpoints, filter enums, category table |
| `servoom/http.py` | transport and the one pagination loop |
| `servoom/pixel_bean_decoder.py` | one decoder per container format (also the web app's decoder) |
| `servoom/layer_file_decoder.py` | the layer-file decoder and PSD/WebP export |
| `servoom/cli.py` | `python -m servoom` |
| `servoom/gallery_reference.py` | preserved probing notes, not used by live code |

## Troubleshooting

- `ImportError: No module named lzallright`: install `lzallright` from PyPI (wheels exist for Windows, macOS and Linux).
- `Format X unsupported`: the decoders cover the formats observed in the wild; a sample of a new one is welcome as an issue.
- Empty pages or throttling: the API caps a page at 30 or 100 items and occasionally throttles; run with `-v` and retry with a smaller `Settings(batch_size=...)`.
