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

export default defineConfig(({ mode }) => ({
  base: resolveBase(mode),
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    headers: securityHeaders,
  },
  preview: {
    host: '0.0.0.0',
    headers: securityHeaders,
  },
}));
