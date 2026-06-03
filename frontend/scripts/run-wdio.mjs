import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { platform } from 'node:os'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const rootDir = resolve(scriptDir, '..')
const launcherSource = resolve(rootDir, 'e2e', 'utils', 'run-hidden-desktop.rs')
const launcherPath = resolve(rootDir, 'node_modules', '.cache', 'vp-e2e', 'run-hidden-desktop.exe')
const wdioCli = resolve(rootDir, 'node_modules', '@wdio', 'cli', 'bin', 'wdio.js')

const args = process.argv.slice(2)
const showIndex = args.indexOf('--show')
const showWindow = process.env.VP_E2E_SHOW_WINDOW === '1' || showIndex !== -1
if (showIndex !== -1) {
  args.splice(showIndex, 1)
}

const wdioArgs = ['run', './wdio.conf.ts', ...args]

const run = (command, commandArgs) => {
  const result = spawnSync(command, commandArgs, {
    cwd: rootDir,
    env: process.env,
    stdio: 'inherit',
    windowsHide: true,
  })
  if (result.error) {
    throw result.error
  }
  process.exit(result.status ?? 1)
}

const ensureHiddenDesktopLauncher = () => {
  const shouldBuild = !existsSync(launcherPath)
    || statSync(launcherPath).mtimeMs < statSync(launcherSource).mtimeMs

  if (!shouldBuild) {
    return launcherPath
  }

  mkdirSync(dirname(launcherPath), { recursive: true })
  const result = spawnSync('rustc', [launcherSource, '-O', '-o', launcherPath], {
    cwd: rootDir,
    stdio: 'inherit',
    windowsHide: true,
  })
  if (result.status !== 0) {
    throw new Error(`failed to build hidden desktop launcher: rustc exited with ${result.status}`)
  }
  return launcherPath
}

if (platform() === 'win32' && !showWindow && process.env.VP_E2E_HIDDEN_DESKTOP !== '0') {
  run(ensureHiddenDesktopLauncher(), [rootDir, process.execPath, wdioCli, ...wdioArgs])
} else {
  run(process.execPath, [wdioCli, ...wdioArgs])
}
