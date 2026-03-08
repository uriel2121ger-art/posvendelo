import { createHash } from 'node:crypto'
import { createReadStream, existsSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { basename, extname, join, relative, resolve } from 'node:path'

const distDir = resolve(process.cwd(), process.env.DIST_DIR || 'dist')
const expectedPlatform = (process.env.DIST_EXPECT_PLATFORM || '').trim().toLowerCase()
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
    const ext = extname(entry.name).toLowerCase()
    if (allowedExtensions.has(ext)) {
      files.push(fullPath)
    }
  }
  return files
}

function classifyArtifact(filePath) {
  const ext = extname(filePath).toLowerCase()
  if (ext === '.appimage' || ext === '.deb' || ext === '.snap') return 'linux'
  if (ext === '.exe' || ext === '.msi' || ext === '.zip') return 'windows'
  return 'unknown'
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

const manifest = {
  generated_at: new Date().toISOString(),
  expected_platform: expectedPlatform || null,
  artifacts: []
}

for (const file of files) {
  const stat = statSync(file)
  const platform = classifyArtifact(file)
  manifest.artifacts.push({
    file: relative(distDir, file),
    name: basename(file),
    platform,
    size_bytes: stat.size,
    sha256: await sha256File(file)
  })
}

if (expectedPlatform) {
  const matching = manifest.artifacts.filter((artifact) => artifact.platform === expectedPlatform)
  if (matching.length === 0) {
    throw new Error(`No se encontraron artefactos para la plataforma esperada: ${expectedPlatform}`)
  }
}

const outputPath = join(distDir, 'dist-manifest.json')
writeFileSync(outputPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
console.log(`Manifest generado en ${outputPath} con ${manifest.artifacts.length} artefacto(s).`)
