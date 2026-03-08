import puppeteer from 'puppeteer-core'
import request from 'request-promise-native'
import { runtimeConfig } from './runtime-config.mjs'
;(async () => {
  try {
    console.log('Conectando al DevTools de Electron...')
    const response = await request(runtimeConfig.devtoolsVersionUrl)
    const webSocketDebuggerUrl = JSON.parse(response).webSocketDebuggerUrl

    const browser = await puppeteer.connect({
      browserWSEndpoint: webSocketDebuggerUrl,
      defaultViewport: null
    })

    const pages = await browser.pages()
    const page =
      pages.find((p) =>
        runtimeConfig.appUrlMatchers.some((candidate) => p.url().startsWith(candidate))
      ) || pages[0]

    console.log(`Página activa: ${page.url()}`)
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
      console.log('Storage purgado por script Puppeteer.')
    })

    await page.reload()
    console.log('Página recargada con Storage limpio. Frontend recuperado.')
    process.exit(0)
  } catch (e) {
    console.error('Error al conectar con Electron DEVTOOLS:', e)
    process.exit(1)
  }
})()
