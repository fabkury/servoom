import { writePsd } from 'ag-psd';
import type { Layer, Psd } from 'ag-psd';
import { decryptAesCbcSync } from './crypto';
import { ensureZstdReady, zstdDecompressSync } from './zstd';

/**
 * Decoder for Divoom "layer files" and exporter to a layered PSD, entirely in the browser.
 *
 * Three container versions are supported. The two current ones start with a byte-0
 * format id followed by a length-prefixed zstd stream (uint32 compressedSize | uint32
 * uncompressedSize | zstd frame) holding the per-frame layer table (num_layers, active
 * layer index, then num_layers x 6-byte descriptors: byte[0] "hidden" flag, byte[1]
 * opacity, uint16 BE hue+180, byte[4] saturation+100, byte[5] lightness+100 -- the
 * editor's HSL sliders). They differ in the pixel section:
 *
 * - 0x27 (39): a second zstd stream of K raw 24-bit RGB layer bitmaps, frame-major
 *   (bottom -> top). The canvas is square, so its side is sqrt(pixels / (3 * K)).
 * - 0x28 (40): K records, each [uint8 flag][uint32 BE length][lossless WEBP image]; each
 *   WEBP is one layer bitmap (RGB, black = transparent, same convention as 0x27).
 *
 * The 2023-2024 container is different:
 *
 * - 0x1D (29): uint32 E | uint32 Z | uint32 R, then E bytes of AES-128-CBC ciphertext
 *   (the artwork key/IV, no padding) followed by plain bytes; decrypted head + plain tail
 *   = Z bytes of zlib that inflate to R bytes. The payload interleaves table and pixels:
 *   per frame [num_layers][active], then per layer the 6-byte descriptor followed by its
 *   side*side*3 RGB bitmap in 16x16-tile order. There is no size field: the side is the
 *   one at which the payload parses exactly with plausible descriptors.
 *
 * See python/layer-tools/LAYER_FILE_FORMAT.md.
 */

const FORMAT_LEGACY = 0x1d;
const FORMAT_RAW_RGB = 0x27;
const FORMAT_WEBP = 0x28;
const LEGACY_HEADER_SIZE = 13;
const LEGACY_SIDES = [16, 32, 64, 128, 256];
const DIVOOM_AES_KEY = new TextEncoder().encode('78hrey23y28ogs89');
const DIVOOM_AES_IV = new TextEncoder().encode('1234567890123456');

export interface LayerFileLayerMeta {
  hidden: boolean;
  opacity: number; // 0-255
  hue: number; // -180..180 (editor slider; bitmaps are stored post-adjustment)
  saturation: number; // -100..100
  lightness: number; // -100..100
}

export interface LayerFileFrameMeta {
  numLayers: number;
  flag: number;
  layers: LayerFileLayerMeta[];
}

export interface DecodedLayerFile {
  format: number; // container format byte: 0x1D, 0x27 or 0x28
  width: number;
  height: number;
  numFrames: number;
  totalLayers: number;
  frames: LayerFileFrameMeta[];
  pixels: Uint8Array; // totalLayers * width * height * 3, RGB
}

function readU32BE(data: Uint8Array, offset: number): number {
  return (
    ((data[offset] << 24) |
      (data[offset + 1] << 16) |
      (data[offset + 2] << 8) |
      data[offset + 3]) >>>
    0
  );
}

/** Read one length-prefixed zstd stream at `pos`; return the bytes and the next offset. */
function readZstdStream(data: Uint8Array, pos: number): { bytes: Uint8Array; next: number } {
  const compressedSize = readU32BE(data, pos);
  const uncompressedSize = readU32BE(data, pos + 4);
  const frame = data.subarray(pos + 8, pos + 8 + compressedSize);
  const decoded = zstdDecompressSync(frame);
  if (decoded.length !== uncompressedSize) {
    throw new Error('Layer stream size mismatch.');
  }
  return { bytes: decoded, next: pos + 8 + compressedSize };
}

/** Decode a lossless WEBP layer bitmap to raw RGB using the browser's image pipeline. */
async function decodeWebpToRgb(webp: Uint8Array): Promise<{ rgb: Uint8Array; side: number }> {
  // Copy into a standalone buffer so the type satisfies BlobPart (subarrays are views).
  const blob = new Blob([new Uint8Array(webp)], { type: 'image/webp' });
  const bitmap = await createImageBitmap(blob, {
    colorSpaceConversion: 'none',
    premultiplyAlpha: 'none',
  });
  const { width, height } = bitmap;
  if (width !== height) {
    bitmap.close();
    throw new Error(`Non-square layer bitmap (${width}x${height}).`);
  }
  const canvas = new OffscreenCanvas(width, height);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) {
    bitmap.close();
    throw new Error('Could not get a 2D context to decode layer WEBP.');
  }
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  const { data: rgba } = ctx.getImageData(0, 0, width, height);
  const rgb = new Uint8Array(width * height * 3);
  for (let i = 0, j = 0; i < rgba.length; i += 4, j += 3) {
    rgb[j] = rgba[i];
    rgb[j + 1] = rgba[i + 1];
    rgb[j + 2] = rgba[i + 2];
  }
  return { rgb, side: width };
}

function parseLayerTable(table: Uint8Array): LayerFileFrameMeta[] {
  const frames: LayerFileFrameMeta[] = [];
  let p = 0;
  while (p + 2 <= table.length) {
    const numLayers = table[p];
    const flag = table[p + 1];
    p += 2;
    const layers: LayerFileLayerMeta[] = [];
    for (let i = 0; i < numLayers; i += 1) {
      layers.push({
        hidden: table[p] !== 0,
        opacity: table[p + 1],
        hue: ((table[p + 2] << 8) | table[p + 3]) - 180,
        saturation: table[p + 4] - 100,
        lightness: table[p + 5] - 100,
      });
      p += 6;
    }
    frames.push({ numLayers, flag, layers });
  }
  return frames;
}

/** Inflate one zlib stream with the browser's built-in decoder. */
async function inflateZlib(stream: Uint8Array): Promise<Uint8Array> {
  const ds = new DecompressionStream('deflate'); // 'deflate' = zlib-wrapped (RFC 1950)
  const writer = ds.writable.getWriter();
  void writer.write(new Uint8Array(stream)).catch(() => undefined);
  void writer.close().catch(() => undefined);
  const buffer = await new Response(ds.readable).arrayBuffer();
  return new Uint8Array(buffer);
}

/**
 * Walk a 0x1D payload at canvas `side`. Returns the frame/layer counts when the payload
 * is consumed exactly, plus whether every header and descriptor looks real (a wrong side
 * can consume the payload too, with pixel bytes read as frame headers); null otherwise.
 */
function scanLegacy(raw: Uint8Array, side: number): { frames: number; layers: number; plausible: boolean } | null {
  const pic = side * side * 3;
  let p = 0;
  let frames = 0;
  let layers = 0;
  let plausible = true;
  while (p < raw.length) {
    if (raw.length - p < 2) return null;
    const n = raw[p];
    const flag = raw[p + 1];
    p += 2;
    if (n === 0 || flag >= n) plausible = false;
    if (raw.length - p < n * (6 + pic)) return null;
    for (let i = 0; i < n; i += 1) {
      // hidden byte above 1, hue+180 above 360, saturation/lightness+100 above 200
      if (raw[p] > 1 || raw[p + 2] > 1 || raw[p + 4] > 200 || raw[p + 5] > 200) plausible = false;
      p += 6 + pic;
    }
    frames += 1;
    layers += n;
  }
  return p === raw.length && frames > 0 ? { frames, layers, plausible } : null;
}

/** 16x16 tiles (row-major tiles, row-major pixels inside) -> row-major bitmap. */
function untile(src: Uint8Array, srcOffset: number, dst: Uint8Array, dstOffset: number, side: number): void {
  const t = side / 16;
  for (let tr = 0; tr < t; tr += 1) {
    for (let tc = 0; tc < t; tc += 1) {
      for (let r = 0; r < 16; r += 1) {
        const s = srcOffset + ((tr * t + tc) * 16 + r) * 48;
        const d = dstOffset + ((tr * 16 + r) * side + tc * 16) * 3;
        dst.set(src.subarray(s, s + 48), d);
      }
    }
  }
}

async function decodeLegacy(data: Uint8Array, sideHint?: number): Promise<DecodedLayerFile> {
  if (data.length < LEGACY_HEADER_SIZE) {
    throw new Error('0x1D layer file shorter than its 13-byte header.');
  }
  const encLen = readU32BE(data, 1);
  const zLen = readU32BE(data, 5);
  const rawLen = readU32BE(data, 9);
  const body = data.subarray(LEGACY_HEADER_SIZE);
  if (encLen % 16 !== 0 || encLen > body.length || zLen > body.length) {
    throw new Error('0x1D layer file: bad header lengths.');
  }
  const stream = new Uint8Array(body);
  stream.set(decryptAesCbcSync(body.subarray(0, encLen), DIVOOM_AES_KEY, DIVOOM_AES_IV), 0);
  const raw = await inflateZlib(stream.subarray(0, zLen));
  if (raw.length !== rawLen) {
    throw new Error(`0x1D layer file: payload size mismatch (header ${rawLen}, got ${raw.length}).`);
  }

  // The hint first, then every square canvas: the first plausible parse wins; a parse that
  // only consumes the payload is the fallback.
  const candidates = sideHint && sideHint % 16 === 0 ? [sideHint, ...LEGACY_SIDES.filter((s) => s !== sideHint)] : LEGACY_SIDES;
  let chosen: { side: number; frames: number; layers: number } | null = null;
  let fallback: { side: number; frames: number; layers: number } | null = null;
  for (const side of candidates) {
    const scan = scanLegacy(raw, side);
    if (!scan) continue;
    if (scan.plausible) {
      chosen = { side, ...scan };
      break;
    }
    if (!fallback) fallback = { side, ...scan };
  }
  chosen = chosen ?? fallback;
  if (!chosen) {
    throw new Error('0x1D layer file: payload does not parse at any Divoom canvas size.');
  }

  const { side } = chosen;
  const pic = side * side * 3;
  const frames: LayerFileFrameMeta[] = [];
  const pixels = new Uint8Array(chosen.layers * pic);
  let p = 0;
  let li = 0;
  for (let f = 0; f < chosen.frames; f += 1) {
    const numLayers = raw[p];
    const flag = raw[p + 1];
    p += 2;
    const layers: LayerFileLayerMeta[] = [];
    for (let i = 0; i < numLayers; i += 1) {
      layers.push({
        hidden: raw[p] !== 0,
        opacity: raw[p + 1],
        hue: ((raw[p + 2] << 8) | raw[p + 3]) - 180,
        saturation: raw[p + 4] - 100,
        lightness: raw[p + 5] - 100,
      });
      p += 6;
      untile(raw, p, pixels, li * pic, side);
      p += pic;
      li += 1;
    }
    frames.push({ numLayers, flag, layers });
  }
  return {
    format: FORMAT_LEGACY,
    width: side,
    height: side,
    numFrames: frames.length,
    totalLayers: chosen.layers,
    frames,
    pixels,
  };
}

/**
 * Decode a layer file. `options.side` is only a hint for the 0x1D container, which carries
 * no canvas size: it is tried first when it parses, else every Divoom size is tried.
 */
export async function decodeLayerFile(data: Uint8Array, options?: { side?: number }): Promise<DecodedLayerFile> {
  const format = data.length ? data[0] : -1;
  if (format === FORMAT_LEGACY) {
    return decodeLegacy(data, options?.side);
  }
  await ensureZstdReady();
  if (format !== FORMAT_RAW_RGB && format !== FORMAT_WEBP) {
    throw new Error('Not a Divoom layer file (expected format 0x1D, 0x27 or 0x28).');
  }

  // Stream 0 (the layer table) is a zstd stream in both container versions.
  const table = readZstdStream(data, 1);
  const frames = parseLayerTable(table.bytes);
  const totalLayers = frames.reduce((sum, f) => sum + f.numLayers, 0);
  if (totalLayers === 0) {
    throw new Error('Layer file declares zero layers.');
  }

  let side: number;
  let pixels: Uint8Array;

  if (format === FORMAT_RAW_RGB) {
    const raw = readZstdStream(data, table.next).bytes;
    side = Math.round(Math.sqrt(raw.length / (3 * totalLayers)));
    if (side * side * 3 * totalLayers !== raw.length) {
      throw new Error('Unexpected layer pixel data size (non-square canvas?).');
    }
    pixels = raw;
  } else {
    // 0x28: K records of [uint8 flag][uint32 BE length][lossless WEBP].
    const rgbLayers: Uint8Array[] = [];
    let p = table.next;
    side = 0;
    for (let i = 0; i < totalLayers; i += 1) {
      if (p + 5 > data.length) {
        throw new Error(`Truncated layer record ${i}.`);
      }
      const length = readU32BE(data, p + 1); // data[p] is a reserved flag byte
      const webp = data.subarray(p + 5, p + 5 + length);
      p += 5 + length;
      const { rgb, side: s } = await decodeWebpToRgb(webp);
      if (side === 0) side = s;
      else if (s !== side) throw new Error('Inconsistent layer bitmap size.');
      rgbLayers.push(rgb);
    }
    const frameSize = side * side * 3;
    pixels = new Uint8Array(totalLayers * frameSize);
    rgbLayers.forEach((rgb, i) => pixels.set(rgb, i * frameSize));
  }

  return {
    format,
    width: side,
    height: side,
    numFrames: frames.length,
    totalLayers,
    frames,
    pixels,
  };
}

function pad(value: number, width: number): string {
  return String(value).padStart(width, '0');
}

/**
 * Build a layered PSD from a Divoom layer file. Each animation frame becomes a layer
 * group; within it, one layer per Divoom layer. Per-layer opacity and the hidden flag
 * are preserved, and black is treated as transparent. Because black is the chroma key,
 * every frame group also gets an opaque black background layer (fNNN_bg) at its bottom,
 * so pixels transparent in all of a frame's layers render black like in the Divoom app.
 * Stacking is bottom -> top (frame 0 and the black background at the bottom, then
 * layer 0), matching the Divoom paint order.
 */
export async function layerFileToPsd(
  data: Uint8Array,
  options?: { allFramesVisible?: boolean },
): Promise<Uint8Array> {
  const decoded = await decodeLayerFile(data);
  const allFramesVisible = options?.allFramesVisible ?? true;
  const side = decoded.width;
  const frameSize = side * side * 3;

  const groups: Layer[] = [];
  let layerIndex = 0;
  for (let f = 0; f < decoded.numFrames; f += 1) {
    const frameMeta = decoded.frames[f];
    // Black is the chroma key: an opaque black background under each frame's layers
    // makes fully-transparent pixels render black, like the Divoom app.
    const bg = new Uint8ClampedArray(side * side * 4);
    for (let o = 3; o < bg.length; o += 4) bg[o] = 255;
    const children: Layer[] = [
      {
        name: `f${pad(f, 3)}_bg`,
        opacity: 1,
        hidden: false,
        left: 0,
        top: 0,
        imageData: new ImageData(bg, side, side),
      },
    ];
    for (let li = 0; li < frameMeta.numLayers; li += 1) {
      const meta = frameMeta.layers[li];
      const base = (layerIndex + li) * frameSize;
      const rgba = new Uint8ClampedArray(side * side * 4);
      let src = base;
      for (let px = 0; px < side * side; px += 1) {
        const r = decoded.pixels[src];
        const g = decoded.pixels[src + 1];
        const b = decoded.pixels[src + 2];
        src += 3;
        const painted = (r | g | b) !== 0; // black (0,0,0) = transparent
        const o = px * 4;
        rgba[o] = r;
        rgba[o + 1] = g;
        rgba[o + 2] = b;
        rgba[o + 3] = painted ? 255 : 0;
      }
      // HSL sliders ride along in the name (only when non-neutral) so they survive a
      // PSD round trip; the hidden tag comes last.
      const hsl =
        meta.hue === 0 && meta.saturation === 0 && meta.lightness === 0
          ? ''
          : `_hue${meta.hue}_sat${meta.saturation}_lit${meta.lightness}`;
      const tag = meta.hidden ? '_HIDDEN' : '';
      children.push({
        name: `f${pad(f, 3)}_l${pad(li, 2)}_op${pad(meta.opacity, 3)}${hsl}${tag}`,
        opacity: meta.opacity / 255,
        hidden: meta.hidden,
        left: 0,
        top: 0,
        imageData: new ImageData(rgba, side, side),
      });
    }
    layerIndex += frameMeta.numLayers;
    // ag-psd: children[0] is the BOTTOM of the stack, so natural order places
    // layer 0 (and frame 0) at the bottom -- matching the Divoom paint order.
    groups.push({
      name: `frame${pad(f, 3)}`,
      opened: false,
      hidden: allFramesVisible ? false : f !== 0,
      children,
    });
  }

  const psd: Psd = { width: side, height: side, children: groups };
  const buffer = writePsd(psd, { generateThumbnail: false });
  return new Uint8Array(buffer);
}
