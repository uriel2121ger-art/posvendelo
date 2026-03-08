import { createHash } from 'node:crypto'
import { createReadStream, existsSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { resolve, join, relative } from 'node:path'

const distDir = resolve(process.cwd(), 'dist')
const allowedExtensions = new Set(['.appimage', '.deb', '.snap', '.exe', '.msi', '.zip'])

function walk(dir) {
  const entries = readdirSync(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const fullPath = join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...walk(fullPath))
      continue
    }
    if (!entry.isFile()) continue
    const lower = entry.name.toLowerCase()
    if ([...allowedExtensions].some((ext) => lower.endsWith(ext))) {
      files.push(fullPath)
    }
  }
  return files
}

function sha256File(path) {
  return new Promise((resolveHash, reject) => {
    const hash = createHash('sha256')
    const stream = createReadStream(path)
    stream.on('data', (chunk) => hash.update(chunk))
    stream.on('end', () => resolveHash(hash.digest('hex')))
    stream.on('error', reject)
  })
}

if (!existsSync(distDir) || !statSync(distDir).isDirectory()) {
  throw new Error('No existe `dist/`. Genera primero los artefactos distribuibles.')
}

const files = walk(distDir).sort()
if (files.length === 0) {
  throw new Error('No se encontraron artefactos distribuibles en `dist/`.')
}

const lines = []
for (const file of files) {
  const checksum = await sha256File(file)
  lines.push(`${checksum}  ${relative(distDir, file)}`)
}

const outputPath = join(distDir, 'SHA256SUMS.txt')
writeFileSync(outputPath, `${lines.join('\n')}\n`, 'utf8')
console.log(`Checksums generados en ${outputPath}`)
