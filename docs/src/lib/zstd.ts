import { Decompressor } from 'zstd-wasm/lib/index.mjs';

let decompressorPromise: Promise<Decompressor> | null = null;
let decompressorInstance: Decompressor | null = null;

export async function ensureZstdReady(): Promise<void> {
  if (decompressorInstance) {
    return;
  }
  if (!decompressorPromise) {
    const instance = new Decompressor();
    decompressorPromise = instance.init();
  }
  decompressorInstance = await decompressorPromise;
}

export function zstdDecompressSync(payload: Uint8Array): Uint8Array {
  if (!decompressorInstance) {
    throw new Error('Zstd module not initialized');
  }
  return decompressorInstance.decompress(payload);
}
