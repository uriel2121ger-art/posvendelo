/**
 * Playwright E2E — Tests en navegador real (PLAN_TESTING_V6).
 * Requiere: backend corriendo en http://127.0.0.1:8000 (API).
 *
 * Levantar frontend: npm run dev:browser
 * Levantar backend: cd backend && set -a && source .env && set +a && uvicorn main:app --host 0.0.0.0 --port 8000
 *
 * Ejecutar E2E: npm run test:e2e
 */
import { defineConfig, devices } from '@playwright/test'

function readEnv(name: string, fallback: string): string {
  const value = process.env[name]?.trim()
  return value || fallback
}

const frontendBaseUrl = readEnv(
  'E2E_BASE_URL',
  readEnv('TITAN_BROWSER_URL', 'http://127.0.0.1:5173')
)
const e2eServerMode = readEnv('E2E_SERVER_MODE', 'dev')
const e2eServerCommand =
  e2eServerMode === 'preview' ? 'node ./scripts/start-e2e-preview.mjs' : 'npm run dev:browser'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: frontendBaseUrl,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Levantar frontend solo con E2E_START_SERVER=1 (por defecto se usa el que ya corre en 5173)
  ...(process.env.E2E_START_SERVER === '1'
    ? {
        webServer: {
          command: e2eServerCommand,
          url: frontendBaseUrl,
          reuseExistingServer: true,
          timeout: 120_000
        }
      }
    : {})
})
