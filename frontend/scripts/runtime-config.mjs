/* eslint-disable @typescript-eslint/explicit-function-return-type */

function readEnv(name, fallback = '') {
  const value = process.env[name]?.trim()
  return value || fallback
}

const browserHost = readEnv('POSVENDELO_BROWSER_HOST', '127.0.0.1')
const browserPort = readEnv('POSVENDELO_BROWSER_PORT', '5173')
const browserOrigin = readEnv('POSVENDELO_BROWSER_URL', `http://${browserHost}:${browserPort}`).replace(
  /\/$/,
  ''
)
const apiBaseUrl = readEnv('POSVENDELO_API_URL', 'http://127.0.0.1:8000').replace(/\/$/, '')
const devtoolsVersionUrl = readEnv(
  'POSVENDELO_DEVTOOLS_VERSION_URL',
  'http://127.0.0.1:9222/json/version'
)
const appUrlMatchers = Array.from(
  new Set(
    [
      browserOrigin,
      readEnv('POSVENDELO_ALT_BROWSER_URL'),
      `http://localhost:${browserPort}`,
      `http://127.0.0.1:${browserPort}`
    ].filter(Boolean)
  )
)

export const runtimeConfig = {
  browserOrigin,
  browserLoginUrl: `${browserOrigin}/#/login`,
  apiBaseUrl,
  devtoolsVersionUrl,
  appUrlMatchers
}
