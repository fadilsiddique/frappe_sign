import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { defineConfig } from 'vitest/config'

// Two entries share one build: staff.html (/sign) and guest.html (/s/<token>). frappe-ui's buildConfig
// copies a single index.html, so it is off; scripts/copy-shells.mjs copies both shells to www/.
export const OUT_DIR = '../frappe_sign/public/frontend'

export default defineConfig(({ mode }) => ({
  plugins: [frappeui({ buildConfig: false }), vue()],
  base: mode === 'production' ? '/assets/frappe_sign/frontend/' : '/',
  build: {
    outDir: OUT_DIR,
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        staff: fileURLToPath(new URL('./staff.html', import.meta.url)),
        guest: fileURLToPath(new URL('./guest.html', import.meta.url)),
      },
      output: {
        // nginx on Frappe Cloud serves .mjs as application/octet-stream, and browsers refuse a module
        // worker (and the import() fallback) with that type: every PDF page stayed blank. Use .js.
        assetFileNames: (asset) =>
          asset.names.some((name) => name.endsWith('.mjs'))
            ? 'assets/[name]-[hash].js'
            : 'assets/[name]-[hash][extname]',
      },
    },
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
    // frappe-ui ships TypeScript and extensionless imports that only Vite resolves.
    server: { deps: { inline: [/frappe-ui/] } },
  },
}))
