import { writePsd } from 'ag-psd';
import type { Layer, Psd } from 'ag-psd';
import { ensureZstdReady, zstdDecompressSync } from './zstd';

/**
 * Decoder for Divoom "layer files" and exporter to a layered PSD, entirely in the browser.
 *
 * Two container versions are supported; both start with a byte-0 format id followed by a
 * length-prefixed zstd stream (uint32 compressedSize | uint32 uncompressedSize | zstd frame)
 * holding the per-frame layer table (num_layers, flag, then num_layers x 6-byte descriptors
 * whose byte[0] is a "hidden" flag and byte[1] is opacity). They differ in the pixel section:
 *
 * - 0x27 (39): a second zstd stream of K raw 24-bit RGB layer bitmaps, frame-major
 *   (bottom -> top). The canvas is square, so its side is sqrt(pixels / (3 * K)).
 * - 0x28 (40): K records, each [uint8 flag][uint32 BE length][lossless WEBP image]; each
 *   WEBP is one layer bitmap (RGB, black = transparent, same convention as 0x27).
 */

const FORMAT_RAW_RGB = 0x27;
const FORMAT_WEBP = 0x28;

export interface LayerFileLayerMeta {
  hidden: boolean;
  opacity: number; // 0-255
}

export interface LayerFileFrameMeta {
  numLayers: number;
  flag: number;
  layers: LayerFileLayerMeta[];
}

export interface DecodedLayerFile {
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
      layers.push({ hidden: table[p] !== 0, opacity: table[p + 1] });
      p += 6;
    }
    frames.push({ numLayers, flag, layers });
  }
  return frames;
}

export async function decodeLayerFile(data: Uint8Array): Promise<DecodedLayerFile> {
  await ensureZstdReady();
  const format = data.length ? data[0] : -1;
  if (format !== FORMAT_RAW_RGB && format !== FORMAT_WEBP) {
    throw new Error('Not a Divoom layer file (expected format 0x27 or 0x28).');
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
 * are preserved, and black is treated as transparent. Stacking is bottom -> top (frame 0
 * and layer 0 at the bottom), matching the Divoom paint order.
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
    const children: Layer[] = [];
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
      const tag = meta.hidden ? '_HIDDEN' : '';
      children.push({
        name: `f${pad(f, 3)}_l${pad(li, 2)}_op${pad(meta.opacity, 3)}${tag}`,
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
