import type { PyodideInterface } from 'pyodide';
import { loadPyodide } from 'pyodide';
import type { PyProxy } from 'pyodide/ffi';
import pixelBeanSource from '../python/pixel_bean.py?raw';
import pixelDecoderSource from '../python/pixel_bean_decoder.py?raw';
import { ensureLzoReady, lzoDecompressSync } from './lzo';
import { ensureZstdReady, zstdDecompressSync } from './zstd';
import { decryptAesCbcSync } from './crypto';
import logger from './logger';

export interface DecodedBean {
  totalFrames: number;
  speed: number;
  rowCount: number;
  columnCount: number;
  frames: Uint8Array[];
  webp: Uint8Array;
  gif: Uint8Array;
}

const STUB_MODULES = `
import sys
import types
from js import Uint8Array
import servoom_codecs

class _LZOCompressor:
    def decompress(self, data, output_size):
        buf = Uint8Array.new(data)
        out = servoom_codecs.lzo_decompress(buf, int(output_size))
        return bytes(out.to_py())

lz_module = types.ModuleType("lzallright")
lz_module.LZOCompressor = _LZOCompressor
sys.modules["lzallright"] = lz_module

class _ZstdDecompressor:
    def decompress(self, data):
        buf = Uint8Array.new(data)
        out = servoom_codecs.zstd_decompress(buf)
        return bytes(out.to_py())

zstd_module = types.ModuleType("zstandard")
zstd_module.ZstdDecompressor = _ZstdDecompressor
sys.modules["zstandard"] = zstd_module

class _AESCipher:
    def __init__(self, key, iv):
        self.key = Uint8Array.new(key)
        self.iv = Uint8Array.new(iv)

    def decrypt(self, payload):
        buf = Uint8Array.new(payload)
        out = servoom_codecs.aes_decrypt(buf, self.key, self.iv)
        return bytes(out.to_py())

aescipher_module = types.ModuleType("AES")
aescipher_module.MODE_CBC = 1

def _aes_new(key, mode, iv):
    return _AESCipher(key, iv)

aescipher_module.new = staticmethod(_aes_new)

cipher_module = types.ModuleType("Cipher")
cipher_module.AES = aescipher_module

crypto_module = types.ModuleType("Crypto")
crypto_module.Cipher = cipher_module

sys.modules["Crypto"] = crypto_module
sys.modules["Crypto.Cipher"] = cipher_module
sys.modules["Crypto.Cipher.AES"] = aescipher_module
`;

const BRIDGE_MODULE = `
from io import BytesIO
from pixel_bean_decoder import PixelBeanDecoder

def decode_pixel_bean(raw_bytes: bytes):
    bean = PixelBeanDecoder.decode_stream(BytesIO(raw_bytes))
    frames = [frame.tobytes() for frame in bean.frames_data]
    webp_buffer = BytesIO()
    bean.save_to_webp(webp_buffer)
    webp_bytes = webp_buffer.getvalue()
    gif_buffer = BytesIO()
    bean.save_to_gif(gif_buffer)
    gif_bytes = gif_buffer.getvalue()
    return {
        "total_frames": bean.total_frames,
        "speed": bean.speed,
        "row_count": bean.row_count,
        "column_count": bean.column_count,
        "frames": frames,
        "webp": webp_bytes,
        "gif": gif_bytes,
    }
`;

function copyBuffer(view: Uint8Array): Uint8Array {
  const cloned = new Uint8Array(view.length);
  cloned.set(view);
  return cloned;
}

function toPlainUint8Array(source: Uint8Array<ArrayBufferLike>): Uint8Array {
  const clone = new Uint8Array(source.length);
  clone.set(source);
  return clone;
}

function registerCodecBridge(pyodide: PyodideInterface): void {
  const bridge = {
    lzo_decompress(input: Uint8Array, expectedLength: number) {
      return lzoDecompressSync(copyBuffer(input), expectedLength);
    },
    zstd_decompress(input: Uint8Array) {
      return zstdDecompressSync(copyBuffer(input));
    },
    aes_decrypt(payload: Uint8Array, key: Uint8Array, iv: Uint8Array) {
      return decryptAesCbcSync(copyBuffer(payload), copyBuffer(key), copyBuffer(iv));
    },
  };
  pyodide.registerJsModule('servoom_codecs', bridge);
}

export class PyodideDecoder {
  private pyodide: PyodideInterface | null = null;
  private readyPromise: Promise<void> | null = null;
  private decodeProxy: PyProxy | null = null;

  async ensureReady(): Promise<void> {
    if (!this.pyodide) {
      if (!this.readyPromise) {
        this.readyPromise = this.initialize();
      }
      await this.readyPromise;
    }
  }

  private async initialize(): Promise<void> {
    logger.info('PyodideDecoder: preparing native bridges');
    await Promise.all([ensureLzoReady(), ensureZstdReady()]);
    logger.info('PyodideDecoder: loading Pyodide');
    this.pyodide = await loadPyodide({
      indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.29.0/full/',
    });
    registerCodecBridge(this.pyodide);
    await this.pyodide.loadPackage(['numpy', 'pillow']);
    try {
      this.pyodide.FS.mkdir('/servoom');
    } catch {
      // already exists
    }
    this.pyodide.FS.writeFile('/servoom/pixel_bean.py', pixelBeanSource);
    this.pyodide.FS.writeFile('/servoom/pixel_bean_decoder.py', pixelDecoderSource);
    this.pyodide.FS.writeFile('/servoom/servoom_bridge.py', BRIDGE_MODULE);
    await this.pyodide.runPythonAsync(`
import sys
sys.path.append('/servoom')
`);
    await this.pyodide.runPythonAsync(STUB_MODULES);
    await this.pyodide.runPythonAsync('from servoom_bridge import decode_pixel_bean');
    this.decodeProxy = this.pyodide.globals.get('decode_pixel_bean');
    logger.info('PyodideDecoder: initialization complete');
  }

  async decode(data: Uint8Array): Promise<DecodedBean> {
    await this.ensureReady();
    if (!this.pyodide || !this.decodeProxy) {
      throw new Error('Pyodide decoder unavailable');
    }
    logger.info('PyodideDecoder: decoding payload', data.length);
    const pyBytes = this.pyodide.toPy(data);
    try {
      const callable = this.decodeProxy as unknown as (arg: PyProxy) => PyProxy;
      const result = callable(pyBytes);
      const jsResult = result.toJs({ dict_converter: Object.fromEntries, create_pyproxies: false }) as {
        total_frames: number;
        speed: number;
        row_count: number;
        column_count: number;
        frames: Uint8Array<ArrayBufferLike>[];
        webp: Uint8Array<ArrayBufferLike>;
        gif: Uint8Array<ArrayBufferLike>;
      };
      result.destroy();
      const frames = jsResult.frames.map((frame) => toPlainUint8Array(frame));
      const webp = toPlainUint8Array(jsResult.webp);
      const gif = toPlainUint8Array(jsResult.gif);
      logger.info('PyodideDecoder: decode complete', {
        frames: frames.length,
        dimensions: `${jsResult.column_count * 16}x${jsResult.row_count * 16}`,
        speed: jsResult.speed,
      });
      return {
        totalFrames: jsResult.total_frames,
        speed: jsResult.speed,
        rowCount: jsResult.row_count,
        columnCount: jsResult.column_count,
        frames,
        webp,
        gif,
      };
    } finally {
      pyBytes.destroy();
    }
  }
}
