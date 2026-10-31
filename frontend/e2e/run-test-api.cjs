const { spawn } = require('node:child_process');
const { rmSync } = require('node:fs');

const python = process.env.SLR_PYTHON;
const databaseDirectory = process.env.SLR_E2E_DB_DIR;
if (!python || !databaseDirectory || !process.env.SLR_DATABASE_PATH) {
  throw new Error('The E2E API requires an explicit Python executable and isolated SQLite path.');
}

const server = spawn(
  python,
  ['-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', '8000'],
  { cwd: process.cwd(), env: process.env, stdio: 'inherit' },
);
let shuttingDown = false;

function cleanup() {
  rmSync(databaseDirectory, { recursive: true, force: true });
}

function stop(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  server.once('exit', () => {
    cleanup();
    process.exit(0);
  });
  server.kill(signal);
  const forceStop = setTimeout(() => server.kill('SIGKILL'), 8000);
  forceStop.unref();
}

server.on('error', (error) => {
  console.error('Failed to start isolated E2E API:', error.message);
  cleanup();
  process.exitCode = 1;
});
server.on('exit', (code) => {
  if (!shuttingDown) {
    cleanup();
    process.exit(code ?? 1);
  }
});

process.on('SIGINT', () => stop('SIGINT'));
process.on('SIGTERM', () => stop('SIGTERM'));
