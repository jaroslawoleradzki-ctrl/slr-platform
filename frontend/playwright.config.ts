import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, '..');
const e2eDatabaseDirectory = mkdtempSync(path.join(os.tmpdir(), 'slr-playwright-e2e-'));
const e2eDatabasePath = path.join(e2eDatabaseDirectory, 'slr-platform.db');
process.env.SLR_E2E_DB_DIR = e2eDatabaseDirectory;
const python = process.env.SLR_PYTHON ?? path.join(repoRoot, '.venv', 'bin', 'python');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:3001',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'node frontend/e2e/run-test-api.cjs',
      cwd: repoRoot,
      url: 'http://127.0.0.1:8000/api/health',
      env: {
        SLR_DATABASE_PATH: e2eDatabasePath,
        SLR_E2E_DB_DIR: e2eDatabaseDirectory,
        SLR_PYTHON: python,
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 3001',
      cwd: frontendRoot,
      url: 'http://127.0.0.1:3001',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
