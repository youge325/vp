import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { resolveE2ECacheDir, rustLauncherCachePath } from '../../../scripts/e2e-cache.mjs'

describe('E2E persistent cache', () => {
  let root: string

  beforeEach(() => {
    root = mkdtempSync(resolve(tmpdir(), 'vp-e2e-cache-'))
  })

  afterEach(() => {
    rmSync(root, { recursive: true, force: true })
  })

  it('prefers the explicit cache directory', () => {
    expect(resolveE2ECacheDir({ VP_E2E_CACHE_DIR: root }, 'win32', 'C:/Users/test')).toBe(root)
  })

  it('uses a cache outside node_modules by default', () => {
    const cacheDir = resolveE2ECacheDir({ LOCALAPPDATA: root }, 'win32', 'C:/Users/test')
    expect(cacheDir).toBe(resolve(root, 'vp-workbench', 'e2e'))
    expect(cacheDir).not.toContain('node_modules')
  })

  it('keys Rust launchers by source content', () => {
    const source = resolve(root, 'launcher.rs')
    writeFileSync(source, 'fn main() {}')
    const first = rustLauncherCachePath(root, source, 'launcher', 'win32')
    expect(first).toBe(rustLauncherCachePath(root, source, 'launcher', 'win32'))
    expect(first).toMatch(/launcher-[a-f0-9]{16}\.exe$/)

    writeFileSync(source, 'fn main() { println!("changed"); }')
    expect(rustLauncherCachePath(root, source, 'launcher', 'win32')).not.toBe(first)
  })
})
