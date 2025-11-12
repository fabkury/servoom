# servoom webapp

Browser-based Divoom toolkit that mirrors the Python CLI without any server-side component. It logs in to the official API, downloads gallery metadata, pulls `.dat` binaries, and decodes them client-side via Pyodide (the original Python decoder compiled to WebAssembly with bridging hooks for AES/LZO/Zstd).

## Prerequisites
- Node.js 18+ (22.x recommended)

## Getting Started
```bash
cd docs
npm install
npm run dev
```
Open the printed local URL, enter your Divoom credentials (plain password or pre-hashed MD5), pick a category, and start decoding. All binaries and WebP exports are generated in-browser; nothing is uploaded.

## Production build
```bash
npm run build
```
The static assets land in `docs/dist/`. Serve them from any static host (GitHub Pages, Netlify, S3, etc.). Because Pyodide relies on `SharedArrayBuffer`, **your host must send** the following HTTP headers for the main HTML file (Vite dev/preview already does this):

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

Once those are in place, the browser will stay cross-origin isolated and the decoder will run entirely on the client.
