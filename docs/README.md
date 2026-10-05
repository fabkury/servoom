# servoom

Browser-based Divoom toolkit that mirrors the Python CLI without any server-side component. It logs in to the official API, downloads gallery metadata, pulls `.dat` binaries, and decodes them client-side via Pyodide (the original Python decoder compiled to WebAssembly with bridging hooks for AES/LZO/Zstd).

## Site layout

The site at servoom.pages.dev has three parts, all built from this folder:

| URL | What | Source |
|-----|------|--------|
| `/` | landing page | `index.html` |
| `/download/` | the download tool described here (React) | `download/index.html`, `src/` |
| `/stats/` | community statistics (plain pages and one chart library) | `public/stats/` |

The statistics data is not in this repository. `scripts/fetch-stats.mjs` downloads the
`data/` folder of [servoom-stats](https://github.com/fabkury/servoom-stats) into
`public/stats/data/` before every `npm run dev` and `npm run build`. The landing and
statistics pages share their text, in the tool's five languages, in
`public/stats/i18n.js`. The design is in [`community-stats/`](community-stats/).

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
The static assets land in `docs/dist/`. Serve them from any static host (GitHub Pages, Netlify, S3, etc.). Because Pyodide relies on `SharedArrayBuffer`, **your host must send** the following HTTP headers for the download tool's page (`public/_headers` sets them for `/download/*`; Vite dev/preview already does this):

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

Once those are in place, the browser will stay cross-origin isolated and the decoder will run entirely on the client.
