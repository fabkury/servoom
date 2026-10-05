import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const securityHeaders = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

function resolveBase(mode: string): string {
  if (mode !== 'production') {
    return '/';
  }

  const target = process.env.DEPLOY_TARGET?.toLowerCase();
  if (target === 'github') {
    return '/servoom/';
  }

  return '/';
}

// Two pages are built: the landing page at / and the download tool at /download/.
// The statistics pages are plain files under public/stats/ and are copied as they are.
export default defineConfig(({ mode }) => ({
  base: resolveBase(mode),
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        download: resolve(__dirname, 'download/index.html'),
      },
    },
  },
  server: {
    host: '0.0.0.0',
    headers: securityHeaders,
  },
  preview: {
    host: '0.0.0.0',
    headers: securityHeaders,
  },
}));
