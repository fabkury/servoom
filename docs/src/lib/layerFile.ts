import { writePsd } from 'ag-psd';
import type { Layer, Psd } from 'ag-psd';
import { ensureZstdReady, zstdDecompressSync } from './zstd';

/**
 * Decoder for Divoom "layer files" (container format 0x27 / 39) and exporter to a
 * layered PSD, entirely in the browser.
 *
 * Container: a 0x27 byte followed by two length-prefixed zstd streams, each
 *   uint32 compressedSize | uint32 uncompressedSize | zstd frame.
 * Stream 0 is a per-frame layer table (num_layers, flag, then num_layers x 6-byte
 * descriptors whose byte[0] is a "hidden" flag and byte[1] is opacity). Stream 1 is
 * K raw 24-bit RGB layer bitmaps, ordered frame-major (bottom -> top). The canvas is
 * square, so its side is sqrt(pixels / (3 * K)).
 */

const FORMAT_ID = 0x27;

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

export async function decodeLayerFile(data: Uint8Array): Promise<DecodedLayerFile> {
  await ensureZstdReady();
  if (data.length === 0 || data[0] !== FORMAT_ID) {
    throw new Error('Not a Divoom layer file (expected format 0x27).');
  }

  const streams: Uint8Array[] = [];
  let pos = 1;
  while (pos + 8 <= data.length) {
    const compressedSize = readU32BE(data, pos);
    const uncompressedSize = readU32BE(data, pos + 4);
    const frame = data.subarray(pos + 8, pos + 8 + compressedSize);
    const decoded = zstdDecompressSync(frame);
    if (decoded.length !== uncompressedSize) {
      throw new Error('Layer stream size mismatch.');
    }
    streams.push(decoded);
    pos += 8 + compressedSize;
  }
  if (streams.length < 2) {
    throw new Error('Layer file did not contain the expected two streams.');
  }

  const table = streams[0];
  const pixels = streams[1];

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

  const totalLayers = frames.reduce((sum, f) => sum + f.numLayers, 0);
  if (totalLayers === 0) {
    throw new Error('Layer file declares zero layers.');
  }
  const side = Math.round(Math.sqrt(pixels.length / (3 * totalLayers)));
  if (side * side * 3 * totalLayers !== pixels.length) {
    throw new Error('Unexpected layer pixel data size (non-square canvas?).');
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
