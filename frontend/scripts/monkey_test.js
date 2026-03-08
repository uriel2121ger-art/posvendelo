/* eslint-disable @typescript-eslint/explicit-function-return-type */
import puppeteer from 'puppeteer-core'
import request from 'request-promise-native'
import { runtimeConfig } from './runtime-config.mjs'

const delay = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  try {
    console.log('Conectando al DevTools de Electron...')
    let response
    for (let i = 0; i < 5; i++) {
      try {
        response = await request(runtimeConfig.devtoolsVersionUrl)
        break
      } catch {
        await delay(2000)
      }
    }
    if (!response) {
      console.error('No se pudo conectar a Electron port 9222')
      process.exit(1)
    }

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

    // Ejecutamos el Gremlin Chaos Monkey
    console.log('Iniciando Chaos Monkey (Clicks & Teclazo)...')
    await page.evaluate(() => {
      window.__monkeyErrors = []
      window.onerror = function (msg) {
        window.__monkeyErrors.push(msg)
        return false
      }

      let keys = ['Enter', 'Escape', 'Tab', 'Backspace', 'F3', 'F12']
      window.__monkeyInterval = setInterval(() => {
        let x = Math.random() * window.innerWidth
        let y = Math.random() * window.innerHeight
        document.elementFromPoint(x, y)?.dispatchEvent(
          new MouseEvent('click', {
            view: window,
            bubbles: true,
            cancelable: true,
            clientX: x,
            clientY: y
          })
        )

        let inputs = document.querySelectorAll('input, textarea')
        if (inputs.length > 0) {
          let randInput = inputs[Math.floor(Math.random() * inputs.length)]
          randInput.value = '-50' // Variante A: negative stock or weird data
          randInput.dispatchEvent(new Event('input', { bubbles: true }))
        }

        document.dispatchEvent(
          new KeyboardEvent('keydown', {
            key: keys[Math.floor(Math.random() * keys.length)],
            bubbles: true
          })
        )
      }, 30)
    })

    await delay(8000)

    const errors = await page.evaluate(() => {
      clearInterval(window.__monkeyInterval)
      console.log('Chaos Monkey Detenido.')
      return window.__monkeyErrors
    })

    console.log('--- RESULTADOS DEL CAOS MONKEY ---')
    console.log(
      'Errores de UI de React detectados:',
      errors.length > 0 ? errors : 'Ninguno. La UI sobrevivió.'
    )

    // Fase 2: Float Precision y FK Deletion usando Fetch API en el contexto de la app
    console.log('Ejecutando Variantes de Backend...')
    const apiResults = await page.evaluate(async (fallbackApiBaseUrl) => {
      const token = localStorage.getItem('titan.token')
      const baseUrl = localStorage.getItem('titan.baseUrl') || fallbackApiBaseUrl
      const res = { floatOk: false, floatError: '', fkOk: false, fkError: '' }

      try {
        // Test FK Deletion
        const cRes = await fetch(`${baseUrl}/api/v1/customers/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ name: 'Monkey Victim', rfc: 'XAXX010101000' })
        })
        const cData = await cRes.json()
        if (cData && cData.id) {
          const dRes = await fetch(`${baseUrl}/api/v1/customers/${cData.id}`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${token}` }
          })
          res.fkOk = !dRes.ok
          res.fkError = await dRes.text()
        } else {
          res.fkError = 'No se pudo crear cliente mono'
        }
      } catch (e) {
        res.fkError = e.message
      }

      return res
    }, runtimeConfig.apiBaseUrl)

    console.log('Resultados de Variantes:', apiResults)

    console.log('Limpiando y saliendo...')
    process.exit(0)
  } catch (e) {
    console.error('Error crítico en script:', e)
    process.exit(1)
  }
})()
