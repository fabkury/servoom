# servoom (C)

The `servoom` library and command-line tool in C99: the read-only Divoom cloud client and
the decoders for every artwork and layer-file container, with output tested
**byte-for-byte** against the Python library on a corpus of several hundred real artworks.
The Python library is the specification; this is the port. Part of
[servoom](../README.md).

## Build

CMake 3.24 or newer, Ninja (or any generator), a C99 compiler, and network access on the
first configure: the codecs are downloaded as pinned release tarballs and built as static
libraries inside `build/`. Nothing is installed system-wide.

```powershell
cd c
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build
```

| Option | Default | Effect |
|--------|---------|--------|
| `SERVOOM_WITH_CLIENT` | ON | build the cloud client (fetches and builds libcurl) |
| `SERVOOM_BUILD_CLI` | ON | build the `servoom` executable |
| `SERVOOM_BUILD_TESTS` | ON | build the test programs |
| `SERVOOM_WITH_WEBP_ENCODER` | ON | build the lossless WebP writer |

TLS comes from Schannel on Windows, Secure Transport on macOS and OpenSSL (`libssl-dev`) on
Linux. If CMake's downloader cannot verify certificates (seen with the WinLibs MinGW
toolchain), point it at a CA bundle:
`-DCMAKE_TLS_CAINFO="C:/Program Files/Git/mingw64/etc/ssl/certs/ca-bundle.crt"`.
Tested with GCC 16 (MinGW-w64) on Windows 11; the code has no platform-specific calls
outside `src/util/fs.c` and `src/client/http.c`.

## Command line

```
servoom info FILE...                        JSON summary + SHA-256 of the decoded frames
servoom decode FILE [-o DIR] [--no-webp]    frames as frame_NNN.ppm / .rgb + NAME.webp
servoom decode-layer FILE [-o DIR] [--no-webp]
                                            composite frames + NAME.webp + raw layer bitmaps
servoom md5 TEXT                            MD5 hex, for SERVOOM_MD5_PASSWORD

servoom list-category CATEGORY [--limit N] [--size MASK] [--type T] [--sort 0|1]
servoom list-user USER_ID [--limit N]
servoom search QUERY [--limit N]
servoom list-experts [--limit N]            ranked artists, one JSON record per line
servoom list-albums [--limit N]
servoom album-arts ALBUM_ID [--limit N]
servoom comments GALLERY_ID [--limit N]     threaded comments, one JSON record per line
servoom forum-posts [--limit N] [--region 1|86] [--tag T]
servoom user-info USER_ID
servoom gallery-info GALLERY_ID                                          (credentials)
servoom download GALLERY_ID [-o DIR] [--no-layer]                        (credentials)
servoom download-user USER_ID [-o DIR] [--limit N]                       (credentials)
```

Credentials are `SERVOOM_EMAIL` with `SERVOOM_MD5_PASSWORD` or `SERVOOM_PASSWORD`, as in
the Python tool; never commit them. Without credentials the cloud commands run
anonymously, which every listing above allows ([`CLOUD_API.md`](../CLOUD_API.md) says
which endpoints need a token), though a category listing then stops after its first
1,230 items.

## Library

`servoom/servoom.h` is the umbrella header. Responses come back as cJSON trees the caller
frees; decoded frames are row-major 24-bit RGB, frame-major, exactly what the Python
`PixelBean.frames_data` holds.

```c
#include "servoom/servoom.h"

servoom_pixel_bean *bean = NULL;
if (servoom_decode_file("601799_Blink.dat", &bean) == SERVOOM_OK) {
    const uint8_t *rgb = servoom_pixel_bean_frame(bean, 0);    /* width*height*3 */
    servoom_pixel_bean_write_webp(bean, "601799_Blink.webp");  /* animated lossless WebP */
    servoom_pixel_bean_free(bean);
}

servoom_layer_bean *layer = NULL;
if (servoom_layer_decode_file("1234_layer.dat", &layer) == SERVOOM_OK) {
    uint8_t *frame = malloc(layer->width * layer->height * 3);
    servoom_layer_composite_frame(layer, 0, frame);            /* app-style composite */
    servoom_layer_bean_free(layer);
}

/* Most listings need no account (CLOUD_API.md, "Anonymous access"). */
servoom_client *a = servoom_client_new_anonymous(NULL);
cJSON *extra = cJSON_CreateObject();
cJSON_AddNumberToObject(extra, "FileSort", SERVOOM_SORT_POPULAR);
cJSON_AddNumberToObject(extra, "FileSize", SERVOOM_SIZE_64 | SERVOOM_SIZE_128);
servoom_client_list_category(a, SERVOOM_CAT_ANIMAL, 90, extra, on_item, userdata);
servoom_client_list_forum_posts(a, SERVOOM_REGION_INTERNATIONAL, -1, 1, 50, on_item, userdata);
cJSON *albums = NULL;
servoom_client_collect(a, SERVOOM_EP_ALBUMS, NULL, 0, &albums);   /* generic call over the table */
servoom_client_free(a);

/* Downloads and the account's own lists need a login. */
char md5[33];
servoom_md5_hex(password, strlen(password), md5);
servoom_client *c = servoom_client_new(email, md5, NULL);
if (servoom_client_login(c) == SERVOOM_OK) {
    char *path = NULL;
    servoom_client_download_artwork(c, 601799, "downloads", &path, NULL);
    free(path);
}
servoom_client_free(c);
```

The client mirrors `DivoomClient` one function per Python method (listings, comments,
users, medals, playlists, albums, the forum feed, the inbox), all read-only, on top of an
endpoint table (`servoom_endpoint_get`) and two generic calls, `servoom_client_lookup` and
`servoom_client_list`. The constants (`servoom_gallery_sort`, `servoom_gallery_size`,
`servoom_gallery_category`, ...) are the ones from `servoom.const`. Listings advance by
the number of items each page returned, because the server caps a page at 30 or 100 items
and truncates larger windows.

| Header | Provides |
|--------|----------|
| `pixel_bean.h` | decode artworks to RGB frames; PPM and WebP output |
| `layer_file.h` | decode layer files (0x27, 0x28) to layer bitmaps and composite frames |
| `client.h` | the cloud client, endpoint table and constants |
| `digest.h` | SHA-256 and MD5 |
| `status.h` | status codes |

### WebP output

`servoom_pixel_bean_write_webp()` produces what `PixelBean.save_to_webp()` produces: an
animated lossless WebP, every frame lasting `speed` ms, looping forever, through the same
libwebp `WebPAnimEncoder` settings Pillow uses. Pixels round-trip exactly. The frame count
may not: libwebp merges runs of identical consecutive frames into one longer frame (as
Pillow does), so the timeline is preserved but a still or an all-identical animation
becomes a plain WebP without timing. The bytes match Pillow's while both link the same
libwebp (1.6.0 today); the tests compare pixels and timeline, never bytes.
`-DSERVOOM_WITH_WEBP_ENCODER=OFF` removes the writer (`servoom_has_webp_encoder()` tells).

## Formats

Artworks: 8, 9, 12 (scrolling banner, decoded as its 64-frame marquee;
`servoom_pixel_bean_banner_strip()` recovers the 64x16 strip), 17, 18, 26 (flat and
hierarchical frames), 31, 41, 42, 43. Layer files: 0x27 (raw RGB) and 0x28 (WebP layers).
What each container holds is documented in [`FILE_FORMATS.md`](../FILE_FORMATS.md).

The port reproduces the Python decoders including their quirks, because the corpus test
demands identical bytes:

- Formats 9/17/18 place 16x16 tiles row-major with the Python tile loop, including the
  non-square multi-panel strips of format 18.
- Format 26 zero-pads 0x0C frames on a non-64x64 canvas; a frame that fails to parse is
  replaced by a copy of the previous one (or black) and decoding continues.
- Format 43 GIFs go through a re-implementation of Pillow's `GifImagePlugin` semantics
  (disposal, palette handling, RGB promotion) and are composited over white with Pillow's
  blend arithmetic; JPEG frames use libjpeg-turbo with Pillow's settings.
- Layer composites round like NumPy (half to even).

## Tests

`ctest --test-dir build` runs three programs:

| Program | What it checks |
|---------|----------------|
| `test_units` | digests, the LZO1X and AES codecs, tile placement, resizing, one synthetic file per format (expected output from the Python decoders, `tests/vectors.h`, regenerated with `python tests/gen_vectors.py`), the WebP writer |
| `test_corpus` | every file of the local reference corpus against `corpus/baseline.json` (frame count, canvas, speed, SHA-256 of all RGB bytes; layer tables and bitmaps for layer files), a WebP round trip per file, and truncated or bit-flipped copies that must never crash (`SERVOOM_NO_MUTATE=1` skips that pass). Skipped without a corpus; see [`corpus/README.md`](../corpus/README.md) |
| `test_live` | the cloud client, first anonymously (page caps across a 70-item window, experts, profiles, medals, search, albums, forum posts, a token-only call that must fail), then logged in with one call to every function. Skipped unless `SERVOOM_EMAIL` and `SERVOOM_PASSWORD` are set |

## Layout

```
include/servoom/   public headers (servoom.h is the umbrella)
src/util/          byte buffers, file I/O, SHA-256, MD5
src/codec/         LZO1X and GIF (in-house), AES-CBC, zstd, JPEG, WebP, compositing, WebP writer
src/decoders/      one file per artwork container format
src/layer/         layer-file decoder
src/client/        libcurl transport, client core, endpoint table, per-method wrappers
cli/main.c         the servoom executable
tests/             unit tests, corpus parity test, live client test
third_party/       vendored single-file libraries (tiny-AES-c, cJSON)
cmake/deps.cmake   fetched dependencies
```

## Dependencies and licenses

| Library | Version | How | License |
|---------|---------|-----|---------|
| tiny-AES-c | 2024-10 | vendored | Unlicense |
| cJSON | 1.7.18 | vendored | MIT |
| zstd | 1.5.7 | FetchContent | BSD-3 / GPLv2 |
| libwebp | 1.6.0 | FetchContent | BSD-3 |
| libjpeg-turbo | 3.1.2 | ExternalProject | IJG / BSD-3 / zlib |
| curl | 8.16.0 | FetchContent | curl (MIT-like) |

LZO1X decompression and the GIF reader are written in-house, so the library carries no
GPL code.
