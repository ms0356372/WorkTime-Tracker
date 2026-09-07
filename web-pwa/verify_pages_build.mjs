import { access, readFile } from 'node:fs/promises'
import { constants } from 'node:fs'

const pagesBase = '/WorkTime-Tracker/'
const requiredFiles = ['dist/index.html', 'dist/manifest.webmanifest', 'dist/sw.js', 'dist/icon.svg']

await Promise.all(requiredFiles.map((file) => access(file, constants.R_OK)))

const manifest = JSON.parse(await readFile('dist/manifest.webmanifest', 'utf8'))
for (const [key, expected] of Object.entries({
  name: '工時管家',
  start_url: pagesBase,
  scope: pagesBase,
  display: 'standalone',
})) {
  if (manifest[key] !== expected) throw new Error(`manifest ${key} must be ${JSON.stringify(expected)}`)
}

for (const icon of manifest.icons ?? []) {
  const pathname = new URL(icon.src, `https://example.test${pagesBase}`).pathname
  if (!pathname.startsWith(pagesBase)) throw new Error(`manifest icon is outside Pages base: ${icon.src}`)
  await access(`dist/${pathname.slice(pagesBase.length)}`, constants.R_OK)
}

const index = await readFile('dist/index.html', 'utf8')
const assetUrls = [...index.matchAll(/(?:src|href)="([^"]+)"/g)].map((match) => match[1])
const generatedAssets = assetUrls.filter((url) => url.includes('/assets/'))
if (!generatedAssets.length) throw new Error('index.html does not reference a generated asset')
if (generatedAssets.some((url) => !url.startsWith(`${pagesBase}assets/`))) {
  throw new Error(`generated asset is outside Pages base: ${generatedAssets.join(', ')}`)
}

console.log(`Verified GitHub Pages build at ${pagesBase}`)
