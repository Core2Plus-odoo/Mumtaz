import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The app is served under /app/ on jewel.mumtaz.digital, next to the landing
// page at / and Odoo on its own prefixes. In development the API calls are
// proxied to a local Odoo so the browser sees one origin and the session
// cookie behaves exactly as it will behind nginx.
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  server: {
    port: 5173,
    proxy: {
      '/jawhar': { target: 'http://127.0.0.1:8069', changeOrigin: false },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
});
