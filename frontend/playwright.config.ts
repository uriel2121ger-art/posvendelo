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

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Levantar frontend solo con E2E_START_SERVER=1 (por defecto se usa el que ya corre en 5173)
  ...(process.env.E2E_START_SERVER === '1'
    ? {
        webServer: {
          command: 'npm run dev:browser',
          url: 'http://localhost:5173',
          reuseExistingServer: true,
          timeout: 60_000
        }
      }
    : {})
})
