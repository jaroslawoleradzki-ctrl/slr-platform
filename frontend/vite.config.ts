import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import { parseAppVersion } from './src/utils/versionParser';

function getAppVersionFromPath(filePath: string): string {
  try {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      return parseAppVersion(content);
    }
  } catch {
    // Fallback on read failure
  }
  return 'development';
}

const appVersion = getAppVersionFromPath(path.resolve(__dirname, '../VERSION'));

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  server: {
    port: 3000,
    open: false,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
