#!/usr/bin/env node
/**
 * Inicia Vite en modo navegador y abre el navegador a los 3 segundos.
 * Uso: node scripts/dev-browser-open.mjs
 * Alternativa si no abre: abre manualmente http://127.0.0.1:5173
 */
import { spawn } from 'node:child_process'
import { platform } from 'node:os'

const URL = 'http://127.0.0.1:5173'

function openBrowser() {
  const cmd =
    platform() === 'win32'
      ? `start "" "${URL}"`
      : platform() === 'darwin'
        ? ['open', URL]
        : ['xdg-open', URL]
  const proc = spawn(
    Array.isArray(cmd) ? cmd[0] : 'cmd',
    Array.isArray(cmd) ? cmd.slice(1) : ['/c', cmd],
    {
      stdio: 'ignore',
      shell: platform() === 'win32'
    }
  )
  proc.on('error', () => {})
}

const child = spawn('npx', ['vite', '--config', 'vite.browser.config.ts'], {
  stdio: 'inherit',
  shell: true
})

setTimeout(openBrowser, 3000)

child.on('exit', (code) => process.exit(code ?? 0))
