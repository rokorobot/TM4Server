import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/', // Serve assets from /static prefix
  build: {
    outDir: '../tm4server/api/static', // Correct output location
    emptyOutDir: true, // Clear old assets first
  }
})
