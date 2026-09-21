# servoom in C

A C99 port of the `servoom` Python library: decoders for every Divoom artwork and layer
file format, plus a Divoom cloud client (login, listings, search, downloads). The Python
library is the specification; the C decoders are tested to produce **byte-identical**
output on a corpus of several hundred real artworks (see [Testing](#testing)).

```
c/
├── include/servoom/     public headers (servoom.h is the umbrella)
│   ├── pixel_bean.h     decode artworks -> RGB frames
│   ├── layer_file.h     decode layer files -> layer bitmaps, composite frames
│   ├── client.h         Divoom cloud client (cJSON responses)
│   ├── digest.h         SHA-256 / MD5 helpers
│   └── status.h         status codes
├── src/
│   ├── util/            byte buffers, file I/O, SHA-256, MD5
│   ├── codec/           LZO1X (in-house), AES-CBC, zstd, JPEG, WebP, GIF (in-house,
│   │                    Pillow-exact), Pillow-style compositing/resizing
│   ├── decoders/        one file per artwork container format + shared helpers
│   ├── layer/           layer-file decoder (0x27 / 0x28)
│   └── client/          libcurl transport + API client
├── cli/main.c           the `servoom` command-line tool
├── tests/               unit tests, corpus parity test, live client test
├── third_party/         vendored single-file libraries (tiny-AES-c, cJSON)
└── cmake/deps.cmake     fetched dependencies (zstd, libwebp, libjpeg-turbo, curl)
```

## Building

Requirements: CMake ≥ 3.24, Ninja (or any generator), a C99 compiler, and network access
the first time you configure (the big codecs are downloaded as pinned release tarballs and
built as static libraries inside `build/`; nothing is installed system-wide).

```powershell
cd c
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build
```

Options:

| Option                  | Default | Effect                                                    |
|-------------------------|---------|-----------------------------------------------------------|
| `SERVOOM_WITH_CLIENT`   | ON      | build the cloud client (fetches and builds libcurl)       |
| `SERVOOM_BUILD_CLI`     | ON      | build `servoom` (`servoom.exe`)                           |
| `SERVOOM_BUILD_TESTS`   | ON      | build the test programs                                   |

On Windows the client uses Schannel (no OpenSSL needed); on macOS Secure Transport; on
Linux OpenSSL (`libssl-dev`). If CMake's downloader cannot verify TLS certificates (seen
with the WinLibs MinGW toolchain), point it at a CA bundle:

```powershell
cmake -S . -B build -G Ninja "-DCMAKE_TLS_CAINFO=C:/Program Files/Git/mingw64/etc/ssl/certs/ca-bundle.crt"
```

Tested with GCC 16 (MinGW-w64, WinLibs) on Windows 11. The code is plain C99 with no
platform-specific calls outside `src/util/fs.c` and `src/client/http.c`, so Linux and
macOS should build as-is.

## Library usage

```c
#include "servoom/servoom.h"

servoom_pixel_bean *bean = NULL;
if (servoom_decode_file("4164515.dat", &bean) == SERVOOM_OK) {
    printf("%d frames, %dx%d, %d ms/frame\n",
           bean->total_frames, bean->width, bean->height, bean->speed);
    const uint8_t *rgb = servoom_pixel_bean_frame(bean, 0); /* width*height*3 */
    servoom_pixel_bean_write_ppm(bean, 0, "frame0.ppm");
    servoom_pixel_bean_free(bean);
}

servoom_layer_bean *layer = NULL;
if (servoom_layer_decode_file("4164515_layer.dat", &layer) == SERVOOM_OK) {
    uint8_t *frame = malloc(layer->width * layer->height * 3);
    servoom_layer_composite_frame(layer, 0, frame);        /* app-style composite */
    const uint8_t *bottom = servoom_layer_bitmap(layer, 0, 0); /* raw layer bitmap */
    servoom_layer_bean_free(layer);
}

char md5[33];
servoom_md5_hex(password, strlen(password), md5);
servoom_client *c = servoom_client_new(email, md5, NULL);
if (servoom_client_login(c) == SERVOOM_OK) {
    cJSON *info = NULL;
    servoom_client_gallery_info(c, 4164515, &info);
    char *path = NULL;
    servoom_client_download_artwork(c, 4164515, "downloads", &path, NULL);
    cJSON_Delete(info); free(path);
}
servoom_client_free(c);
```

Decoded frames are row-major 24-bit RGB, frame-major, exactly what the Python
`PixelBean.frames_data` holds. The library only decodes; it writes no WebP/GIF/PSD files
(the Python library and the web app do that).

Supported artwork formats: 9, 17, 18, 26 (0x0C and hierarchical 0x11/0x13/0x15 frames),
31, 41, 42, 43 (embedded GIF or WebP). Layer files: 0x27 (raw RGB) and 0x28 (WebP layers).

### Parity notes

The port reproduces the Python decoders *including their quirks*, because the corpus
test demands identical bytes. Some are worth knowing:

* Formats 9/17/18 place 16x16 tiles with the Python `_compact` loop, whose tile column
  wraps at `row_count` (fine for square canvases, which is all Divoom produces).
* Format 26 with 0x0C frames on a non-64x64 canvas zero-pads each 4096-pixel frame to the
  canvas (Python's `_frames_from_rgb`).
* Frames that fail to parse in format 26 are replaced by a copy of the previous frame (or
  a black frame), and decoding continues at the next declared offset.
* Format 43 GIFs are decoded with a re-implementation of Pillow's `GifImagePlugin`
  semantics (sticky disposal method, palette handling, RGB-after-first-frame promotion)
  and composited over white with Pillow's `paste` blend arithmetic. JPEG frames go
  through libjpeg-turbo with Pillow's settings (ISLOW IDCT, fancy upsampling).
* The layer-file composite rounds like NumPy (`round` half to even).

## Command-line tool

```
servoom info FILE...                       JSON summary + SHA-256 of the decoded frames
servoom decode FILE [-o DIR]               frames as frame_NNN.ppm / .rgb
servoom decode-layer FILE [-o DIR]         composite frames + raw layer bitmaps (.rgb)
servoom md5 TEXT                           MD5 hex (to produce SERVOOM_MD5_PASSWORD)
servoom gallery-info GALLERY_ID            GalleryInfo JSON                  (credentials)
servoom download GALLERY_ID [-o DIR]       artwork + its layer file          (credentials)
servoom download-user USER_ID [-o DIR] [--limit N]                           (credentials)
servoom list-category CATEGORY [--limit N] [--size MASK] [--type T]          (credentials)
```

Credentials: `SERVOOM_EMAIL` plus `SERVOOM_MD5_PASSWORD` or `SERVOOM_PASSWORD`, as in the
Python CLI. Never commit them.

## Testing

`ctest --test-dir build` runs three programs:

* **test_units** — digests, the LZO1X and AES codecs, tile placement, resizing, and
  synthetic container files for every format whose expected output was produced by the
  Python decoders (`tests/vectors.h`, regenerated with `python tests/gen_vectors.py`).
* **test_corpus** — decodes every file in the shared reference corpus (`../corpus/`) and
  compares frame count, canvas, speed and the SHA-256 of all decoded RGB bytes with
  `corpus/baseline.json`, the Python decoders' output. Layer files additionally compare the
  parsed layer table and the raw layer bitmaps. Skipped (exit 77) when the corpus payloads
  are not present locally; see `../corpus/README.md` for how to fetch them.
* **test_live** — logs in to the Divoom cloud, fetches gallery info, runs a listing, and
  downloads and decodes an artwork. Skipped unless `SERVOOM_EMAIL`/`SERVOOM_PASSWORD` are
  set.

## Dependencies and licenses

| Library         | Version | How            | License                |
|-----------------|---------|----------------|------------------------|
| tiny-AES-c      | 2024-10 | vendored       | Unlicense              |
| cJSON           | 1.7.18  | vendored       | MIT                    |
| zstd            | 1.5.7   | FetchContent   | BSD-3 / GPLv2          |
| libwebp         | 1.6.0   | FetchContent   | BSD-3                  |
| libjpeg-turbo   | 3.1.2   | ExternalProject| IJG / BSD-3 / zlib     |
| curl            | 8.16.0  | FetchContent   | curl (MIT-like)        |

LZO1X decompression and the GIF reader are written in-house (no minilzo/giflib), so the
library carries no GPL code.
