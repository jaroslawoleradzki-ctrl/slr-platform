import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';
import { parseAppVersion } from './src/utils/versionParser';

const appVersion = parseAppVersion(fs.readFileSync(path.resolve(__dirname, '../VERSION'), 'utf-8'));

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
  },
});
