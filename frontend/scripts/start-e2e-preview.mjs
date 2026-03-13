import { spawn } from 'node:child_process'

const frontendBaseUrl = process.env.E2E_BASE_URL?.trim() || process.env.POSVENDELO_BROWSER_URL?.trim()
const apiBaseUrl = process.env.E2E_API_URL?.trim() || process.env.POSVENDELO_API_URL?.trim()

if (!frontendBaseUrl) {
  throw new Error('E2E_BASE_URL o POSVENDELO_BROWSER_URL es requerido para arrancar preview de E2E.')
}

const parsed = new URL(frontendBaseUrl)
const port = parsed.port || (parsed.protocol === 'https:' ? '443' : '80')

const sharedEnv = {
  ...process.env,
  POSVENDELO_BROWSER_PORT: port,
  POSVENDELO_BROWSER_URL: frontendBaseUrl,
  ...(apiBaseUrl ? { POSVENDELO_API_URL: apiBaseUrl } : {})
}

const build = spawn('npm', ['run', 'build:browser'], {
  stdio: 'inherit',
  shell: true,
  env: sharedEnv
})

build.on('exit', (code) => {
  if (code && code !== 0) {
    process.exit(code)
    return
  }

  const preview = spawn(
    'npx',
    ['vite', 'preview', '--config', 'vite.browser.config.ts', '--host', '127.0.0.1'],
    {
      stdio: 'inherit',
      shell: true,
      env: sharedEnv
    }
  )

  preview.on('exit', (previewCode) => {
    process.exit(previewCode ?? 0)
  })
})
