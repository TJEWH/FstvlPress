import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const DEFAULT_APP_DISPLAY_NAME = 'FstvlPress'

function getAppDisplayName(mode) {
  const env = loadEnv(mode, process.cwd(), '')
  return env.VITE_APP_DISPLAY_NAME || env.APP_DISPLAY_NAME || DEFAULT_APP_DISPLAY_NAME
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const appDisplayName = getAppDisplayName(mode)

  return {
    define: {
      __APP_DISPLAY_NAME__: JSON.stringify(appDisplayName),
    },
    plugins: [
      vue(),
      {
        name: 'app-display-name-html',
        transformIndexHtml(html) {
          return html.replace(/%APP_DISPLAY_NAME%/g, escapeHtml(appDisplayName))
        },
      },
    ],
    server: {
      proxy: {
        '/api/v1': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/openapi.json': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/health': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/sitemap.xml': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/robots.txt': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/download': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/oidc-proxy': {
          target: 'http://localhost:8180',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/oidc-proxy/, ''),
        },
      },
    },
  }
})
