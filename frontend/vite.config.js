import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  base: './',   // relative asset paths, needed for electron file:// loading
  server: {
    // dev only - production goes through nginx
    proxy: {
      '/config':   'http://localhost:8000',
      '/metrics':  'http://localhost:8000',
      '/prices':   'http://localhost:8000',
      '/settings': 'http://localhost:8000',
    },
  },
});
