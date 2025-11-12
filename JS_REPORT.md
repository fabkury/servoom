# Browser Port Feasibility Report

## Purpose
Assess what it would take to port the existing `servoom` Python tooling into a static, client-side web application that can call the Divoom API, pull metadata, download binary `.dat` payloads, decode every supported animation format, and let users export the same artifacts that the CLI currently produces.

## Current Capabilities & Scope
- **Data coverage** – The CLI already wraps every endpoint required to enumerate uploads, likes, tags, comments, and feeds (see `Config` constants in `servoom/config.py:13-115`). Pagination, retries, and column mapping logic are coded in `servoom/client.py:64-200` and `servoom/cli.py:66-155`.
- **Binary handling** – `APIxoo.download()` sanitizes names, caches raw `.dat` files, and always funnels the payload through the `PixelBeanDecoder` (`servoom/api_client.py:197-248`).
- **Decoder surface** – `PixelBeanDecoder` supports formats 9, 17, 18, 26, 31, 42, and 43 (declared in `servoom/cli.py:5-13` and `servoom/pixel_bean_decoder.py:16-1038`). Each format uses AES-CBC, LZO, bit-level palette decoding, Zstandard, or embedded GIF/WEBP parsing.
- **Rendering/export** – `PixelBean` stores frames as numpy arrays and uses Pillow to emit WebP animations with per-frame delays (`servoom/pixel_bean.py:36-159`).

The browser port must therefore replicate four pillars: authentication + HTTP orchestration, metadata shaping + CSV export, binary download + caching, and the full decoder/rendering stack.

## Feasibility Snapshot
| Area | Feasible? | Notes |
| --- | --- | --- |
| API access from browser | **Likely** | Both `https://app.divoom-gz.com` and `https://f.divoom-gz.com` return permissive CORS headers (`Access-Control-Allow-Origin: *`), so `fetch` can reproduce the current POST flows directly from the client. |
| Credentials | **Risky but manageable** | Users must type their email and (hashed) password in the page. MD5 hashing can happen locally before calling `/UserLogin`, but the UX must stress the security model. |
| Metadata processing | **Straightforward** | Replace pandas/tqdm with in-browser arrays and UI components; CSV export can rely on Blob objects. |
| Binary decode | **Complex but doable** | All algorithms are deterministic and can be ported to TypeScript + WebAssembly. The heaviest pieces are AES, LZO (`lzallright`), Pillow image parsing, and Zstd. Existing C/C++ libs can be compiled to WASM. |
| Animation export | **Doable with WASM/WebCodecs** | Use `libwebp` WASM or the WebCodecs API to assemble WebP files, and offer `download` links via `URL.createObjectURL`. |

## Functional Areas & Browser Strategy

### 1. Authentication & Session Management
- Browser UI prompts for email + password, hashes password with `crypto.subtle.digest('MD5', …)` before hitting `/UserLogin` (see `APIxoo.log_in()` in `servoom/api_client.py:77-98`).
- Tokens returned by the login call must be kept only in memory (React/Vue state or a dedicated context). Persisting access tokens in local storage would leak accounts.
- Rate limits and retry logic from `DivoomClient.fetch_*` loops (`servoom/client.py:96-200`) can be translated into async iterators that back off using `setTimeout`.

### 2. Metadata Fetching & CSV Export
- Reuse the payload shapes already encoded in `Config.FIELD_MAPPINGS` (`servoom/config.py:74-115`) to map server fields to friendly column names.
- Instead of pandas, keep metadata in plain objects/typed arrays and render them in tables. For CSV export, serialize rows with `Array.join(',')`, feed them into a Blob, and trigger a download.
- The progress indicators currently handled by `tqdm` should become UI progress bars bound to state derived from pagination counters.

### 3. Binary Downloading & Client Storage
- Use the same URLs (`Server.FILE` in `servoom/const.py:48-55`) with `fetch` + `response.arrayBuffer()`.
- In lieu of filesystem caches (`raw_data/*.bin`), store ArrayBuffers inside IndexedDB (keyed by `file_type`, gallery ID, and dimensions) and expose a UI toggle to purge cached blobs.
- To let users “download what servoom would write,” create Blob URLs for both the raw `.dat` payload and the decoded WebP, then attach them to `<a download>` elements.

### 4. Pixel Bean Decoding Pipeline
1. **Parsing header** – Implement the same byte-order logic baked into `PixelBeanDecoder.decode_stream()` (`servoom/pixel_bean_decoder.py:1416-1451`) using `DataView`.
2. **AES-CBC decrypt** – Mirror `_decrypt_aes` (`servoom/pixel_bean_decoder.py:26-44`) via the WebCrypto `SubtleCrypto.decrypt` API initialized with the hard-coded key/IV.
3. **LZO decompression (formats 9/18/26)** – Port `lzallright` by compiling `liblzo` to WebAssembly, or adopt an existing JS LZO decoder. Wrap it behind the same interface as `_lzo.decompress`.
4. **Custom palette logic for format 26** – Transcribe the bit-manipulation routines in `AnimMulti64Decoder` and `Decoder0x1A` (`servoom/pixel_bean_decoder.py:1095-1388`). Typed arrays and bitwise math translate directly to JavaScript.
5. **Zstd (format 42)** – Use `zstd-codec` or compile the reference implementation to WASM to reproduce `zstandard.ZstdDecompressor` usage (`servoom/pixel_bean_decoder.py:1002-1039`).
6. **Embedded GIF/WEBP (format 43) & JPEG (format 31)** – Replace Pillow with the browser’s native decoders: feed extracted GIF/WEBP/JPEG blobs into `<img>` / `createImageBitmap` or `OffscreenCanvas` to rasterize frames, as the Python code currently leverages `PIL.ImageSequence` (`servoom/pixel_bean_decoder.py:1042-1154` and `1263-1356`).
7. **Frame assembly** – Use `Uint8ClampedArray` buffers to mimic the numpy grids inside `_compact` (`servoom/pixel_bean_decoder.py:45-100`) and then wrap them in `ImageData` objects for display/export.

### 5. Rendering & WebP Encoding
- The Python path calls `PixelBean.save_to_webp()` (`servoom/pixel_bean.py:130-159`). On the web, schedule a Web Worker dedicated to encoding to avoid blocking the UI thread.
- Options: (a) compile `libwebp` to WASM, (b) use the emerging WebCodecs `ImageEncoder` with `type: 'image/webp'`, or (c) temporarily export animated PNG/GIF via `gifenc`-style WASM if WebP support is insufficient.

### 6. Testing & Regression
- Reuse the assets in `reference-animations/` and the smoke script (`run_tests.py`) as golden files by turning them into fixtures that the browser can load (drag-and-drop or fetched from the site itself). Compare decoded frames with precomputed hashes using WebAssembly-ported numpy-lite routines.

## Principal Challenges & Mitigations
1. **Security & Credentials Exposure**  
   - *Challenge:* The CLI stores MD5 hashes locally; a web page would require the user to enter credentials, exposing them to the page’s JS.  
   - *Mitigation:* Open-source the site so users can self-host, compute the MD5 strictly in-memory, and offer an “advanced” option to paste the MD5 hash directly so raw passwords never touch the code. Also, add a prominent warning banner explaining the trust model.

2. **Binary Parsing Performance**  
   - *Challenge:* 256×256×3×N byte buffers plus decrypt/decompress steps can freeze the UI.  
   - *Mitigation:* Offload decoding into Web Workers and share ArrayBuffers via `postMessage({transfer: [...]})`. Measure memory (Chrome has ~2 GB per tab) and stream frames incrementally so previews appear while decoding finishes.

3. **Replacing Native Libraries**  
   - *Challenge:* `lzallright`, `zstandard`, and Pillow lack direct browser equivalents.  
   - *Mitigation:* Compile these dependencies to WebAssembly once and distribute them as static assets; each module exposes the same procedural API that the Python code expects. AES rides on WebCrypto so no WASM is needed there.

4. **WebP / GIF Encoding Fidelity**  
   - *Challenge:* Lossless animation encoding must honor frame delays (`speed`) and loop/disposal flags, mirroring Pillow’s behavior (`servoom/pixel_bean.py:151-158`).  
   - *Mitigation:* Use WebCodecs or libwebp to explicitly set `duration`, `loop`, and `lossless` fields; add automated comparisons against the CLI outputs to ensure frame counts and timestamps match.

5. **Offline Caching & Download UX**  
   - *Challenge:* The CLI leaves `.dat` and `.webp` on disk; the browser must provide an equivalent experience.  
   - *Mitigation:* Maintain an IndexedDB store keyed by gallery ID to cache raw payloads. Offer “Export Raw” and “Export WebP” buttons that call `URL.createObjectURL` so the browser prompts for downloads, satisfying the user requirement that “files are downloaded from the page.”

6. **Rate Limits & Long-Running Jobs**  
   - *Challenge:* Fetching every upload/like can involve thousands of requests.  
   - *Mitigation:* Mirror the pagination loops from `DivoomClient` (batch size 50) and throttle using `AbortController` so the user can pause/cancel jobs. Display incremental progress counters that reference the same debug stats found in the CLI.

## Recommended Architecture
1. **Tech stack** – TypeScript + Vite (or Next.js static export) for the UI, Tailwind or similar for styling, Zustand/Redux for session state.
2. **Workers** – Dedicated worker for Divoom API calls (keeps tokens isolated) and another worker for decode/encode pipelines that loads the WASM modules (LZO, zstd, libwebp).
3. **Modules** – A `decoder` package that mirrors the Python class hierarchy (per-format decoder classes), plus `pixel-bean.ts` that implements the same frame container contract used throughout the UI.
4. **Storage** – IndexedDB (via `idb` library) for cached raw blobs + decoded previews, and `File System Access API` (optional) for power users who want to write directly to disk.
5. **Testing** – Jest or Vitest snapshots comparing browser-decoded frames vs. the reference PNG/WebP files from `reference-animations/`.
6. **Deployment** – Static assets on any CDN/GitHub Pages; no server component required thanks to the permissive CORS headers observed on both API hosts.

## Implementation Roadmap
1. **Prototype login + metadata fetch** – Build a simple form that logs in and lists gallery files to prove the CORS posture really works in browsers.  
2. **Port PixelBean container to JS** – Implement the frame assembly + preview rendering path with fake/test data.  
3. **Integrate format 9 & 18 decoders** – Start with AES + LZO flows, since they are the most common.  
4. **Add format 26/31/42/43 support** – Tackle each format in order of complexity, introducing the necessary WASM dependencies one by one.  
5. **Ship WebP exporter + download buttons** – Ensure the encoded result matches the Python CLI across the `reference-animations` suite.  
6. **Polish UX** – Progress indicators, cancel buttons, cache management UI, and documentation that mirrors `README.md`.

## Conclusion
Every piece of functionality in `servoom` maps to browser primitives, but the binary-decoder pipeline requires careful reimplementation with WebAssembly, Web Workers, and modern Web APIs. With those investments, a fully client-side tool is achievable, keeps user data local, and aligns with the requirement that “everything runs in the browser” while still matching the breadth of the current Python tooling.

---

## Implementation Status (Nov 2025)

The `webapp/` directory now ships a working version of this architecture:

- **Decoder parity via Pyodide.** Instead of partially re-writing the Python decoder, the site loads Pyodide (CPython compiled to WebAssembly), mounts the original `pixel_bean.py`/`pixel_bean_decoder.py`, and bridges the native dependencies (`lzallright`, `zstandard`, `Crypto.Cipher.AES`) to synchronous JS/WASM helpers (`lzo-wasm`, `zstd-wasm`, `aes-js`). This keeps Format 9/17/18/26/31/42/43 coverage identical to the CLI.
- **End-to-end client workflow.** A React/Vite SPA (`npm run dev` in `webapp/`) exposes login, category pagination, binary download, live animation preview, and two download buttons (raw `.dat` + Pillow-rendered WebP returned directly from Pyodide).
- **No backend.** All traffic goes straight from the browser to `app.divoom-gz.com` / `f.divoom-gz.com`; Pyodide assets stream from the official CDN on demand, and binaries/WebP exports are served via `URL.createObjectURL`.

See `webapp/README.md` for setup commands and deployment notes.
