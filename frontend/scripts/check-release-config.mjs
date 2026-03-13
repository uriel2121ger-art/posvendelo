import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const configPath = resolve(process.cwd(), 'electron-builder.yml')
const raw = readFileSync(configPath, 'utf8')

const checks = [
  {
    id: 'appId',
    ok: !/^\s*appId:\s*com\.electron\.app\s*$/m.test(raw),
    message:
      "appId sigue con valor placeholder ('com.electron.app'). Define uno real, por ejemplo: com.posvendelo.pos"
  },
  {
    id: 'productName',
    ok: !/^\s*productName:\s*electron_pos\s*$/m.test(raw),
    message:
      "productName sigue con valor placeholder ('electron_pos'). Define el nombre comercial real."
  },
  {
    id: 'executableName',
    ok: !/^\s*executableName:\s*electron_pos\s*$/m.test(raw),
    message:
      "executableName sigue con valor placeholder ('electron_pos'). Define el binario distribuible real."
  },
  {
    id: 'maintainer',
    ok: !/^\s*maintainer:\s*electronjs\.org\s*$/m.test(raw),
    message: "maintainer sigue con valor placeholder ('electronjs.org'). Define el mantenedor real."
  },
  {
    id: 'publishUrl',
    ok: !/^\s*url:\s*https:\/\/example\.com\/auto-updates\s*$/m.test(raw),
    message:
      "publish.url sigue con valor placeholder ('https://example.com/auto-updates'). Define endpoint real de updates."
  }
]

const failed = checks.filter((item) => !item.ok)

const requiredPaths = [
  {
    id: 'desktopIcon',
    ok: existsSync(resolve(process.cwd(), 'resources/icon.png')),
    message: 'Falta `resources/icon.png`; el build distribuible usará icono genérico de Electron.'
  }
]

const failedPaths = requiredPaths.filter((item) => !item.ok)

if (failed.length > 0 || failedPaths.length > 0) {
  console.error('Release config validation failed:')
  for (const issue of failed) {
    console.error(`- [${issue.id}] ${issue.message}`)
  }
  for (const issue of failedPaths) {
    console.error(`- [${issue.id}] ${issue.message}`)
  }
  process.exit(1)
}

console.log('Release config validation passed.')
