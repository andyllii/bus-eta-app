import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev proxy: route /api/* (and /v1/*) to the running FastAPI backend so the
// browser never hits a CORS wall and we keep a relative base URL in the client.
const API_TARGET = process.env.VITE_API_TARGET || 'http://localhost:8000';

// GitHub Pages serves this at https://andyllii.github.io/bus-eta-app/
const BASE = process.env.VITE_BASE || '/bus-eta-app/';

export default defineConfig({
  base: BASE,
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/v1': { target: API_TARGET, changeOrigin: true },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/v1': { target: API_TARGET, changeOrigin: true },
    },
  },
});
