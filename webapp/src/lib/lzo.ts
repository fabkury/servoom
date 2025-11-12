import createModule from 'lzo-wasm/lzo-wasm.js';
import wasmUrl from 'lzo-wasm/lzo-wasm.wasm?url';

type LzoModule = Awaited<ReturnType<typeof createModule>>;

let modulePromise: Promise<LzoModule> | null = null;
let moduleInstance: LzoModule | null = null;
let decompressFn: ((inputPtr: number, inputLength: number, outputLength: number) => number) | null = null;

export async function ensureLzoReady(): Promise<void> {
  if (moduleInstance) {
    return;
  }
  if (!modulePromise) {
    modulePromise = createModule({
      locateFile: () => wasmUrl,
    });
  }
  moduleInstance = await modulePromise;
  decompressFn = moduleInstance.cwrap('decompress', 'number', ['number', 'number', 'number']);
}

export function lzoDecompressSync(input: Uint8Array, expectedLength: number): Uint8Array {
  if (!moduleInstance || !decompressFn) {
    throw new Error('LZO module not initialized');
  }

  const inputLength = input.length;
  const inputPtr = moduleInstance._malloc(inputLength);
  moduleInstance.HEAPU8.set(input, inputPtr);

  try {
    const outputPtr = decompressFn(inputPtr, inputLength, expectedLength);
    const view = new Uint8Array(moduleInstance.HEAPU8.buffer, outputPtr, expectedLength);
    const copy = new Uint8Array(view);
    moduleInstance._free(outputPtr);
    return copy;
  } finally {
    moduleInstance._free(inputPtr);
  }
}
