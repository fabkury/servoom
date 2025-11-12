import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const securityHeaders = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    headers: securityHeaders,
  },
  preview: {
    host: '0.0.0.0',
    headers: securityHeaders,
  },
});
