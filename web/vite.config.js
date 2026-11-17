import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  // During `pnpm dev`, send /api calls to the FastAPI server
  // (API_URL is set by compose.dev.yaml, where the server is called "api")
  server: { proxy: { '/api': process.env.API_URL || 'http://localhost:8000' } },
})