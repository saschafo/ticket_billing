import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'
import path from 'path'

// Port des laufenden bench-Webservers, damit "npm run dev" gegen eine lokale
// Bench proxyen kann. Ausserhalb einer Bench (z. B. im Docker-Build) gibt es
// die Datei nicht -- dann bleibt es beim Standardport.
const webserver_port = (() => {
  try {
    const cfg = path.resolve(__dirname, '../../../../sites/common_site_config.json')
    return JSON.parse(fs.readFileSync(cfg, 'utf-8')).webserver_port || 8000
  } catch {
    return 8000
  }
})()

export default defineConfig({
  plugins: [vue()],

  // Feature-Flags von vue-i18n. Ohne sie warnt der Build, und die
  // Legacy-API landet unnoetig im Bundle.
  define: {
    __VUE_I18N_FULL_INSTALL__: true,
    __VUE_I18N_LEGACY_API__: false,
    __INTLIFY_PROD_DEVTOOLS__: false,
  },

  server: {
    port: 8083,
    proxy: {
      '/api': { target: `http://127.0.0.1:${webserver_port}`, changeOrigin: true },
      '/assets': { target: `http://127.0.0.1:${webserver_port}`, changeOrigin: true },
      '/files': { target: `http://127.0.0.1:${webserver_port}`, changeOrigin: true },
    },
  },

  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },

  build: {
    // Landet im public-Ordner der App und wird von Frappe unter
    // /assets/ticket_billing/frontend/ ausgeliefert. Das Ergebnis wird
    // mitcommittet -- der Docker-Build braucht dadurch keinen Node-Schritt.
    outDir: '../public/frontend',
    emptyOutDir: true,
    target: 'es2015',
    rollupOptions: {
      output: {
        // Feste Dateinamen ohne Hash, damit www/ticketbilling.html sie
        // unveraendert referenzieren kann.
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/index.[ext]',
      },
    },
  },

  base: '/assets/ticket_billing/frontend/',
})
