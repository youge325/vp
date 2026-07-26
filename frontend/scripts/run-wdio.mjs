import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { platform } from 'node:os'
import net from 'node:net'
import { resolveE2ECacheDir, rustLauncherCachePath } from './e2e-cache.mjs'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const rootDir = resolve(scriptDir, '..')
const launcherSource = resolve(rootDir, 'tests', 'e2e', 'utils', 'run-hidden-desktop.rs')
const e2eCacheDir = resolveE2ECacheDir()
const launcherPath = rustLauncherCachePath(e2eCacheDir, launcherSource, 'run-hidden-desktop')
const wdioCli = resolve(rootDir, 'node_modules', '@wdio', 'cli', 'bin', 'wdio.js')
const networkProxyVariables = new Set([
  'all_proxy',
  'global_agent_http_proxy',
  'global_agent_https_proxy',
  'http_proxy',
  'https_proxy',
  'no_proxy',
  'node_use_env_proxy',
  'npm_config_https_proxy',
  'npm_config_noproxy',
  'npm_config_proxy',
])

const args = process.argv.slice(2)
const showIndex = args.indexOf('--show')
const showWindow = process.env.VP_E2E_SHOW_WINDOW === '1' || showIndex !== -1
if (showIndex !== -1) {
  args.splice(showIndex, 1)
}

const wdioArgs = ['run', './wdio.conf.ts', ...args]

const canListenOnPort = (port, host = '127.0.0.1') => new Promise((resolveListen) => {
  const server = net.createServer()
  server.once('error', () => {
    resolveListen(false)
  })
  server.listen(port, host, () => {
    server.close(() => {
      resolveListen(true)
    })
  })
})

const findAvailablePort = async (usedPorts) => {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    const port = 30000 + Math.floor(Math.random() * 10000)
    if (usedPorts.has(port)) {
      continue
    }
    if (await canListenOnPort(port)) {
      usedPorts.add(port)
      return port
    }
  }
  throw new Error('unable to resolve available WebDriver port')
}

const withoutNetworkProxy = (environment) => Object.fromEntries(
  Object.entries(environment).filter(([name]) => !networkProxyVariables.has(name.toLowerCase())),
)

const reservedPorts = new Set()
if (!process.env.VP_TAURI_DRIVER_PORT || Number(process.env.VP_TAURI_DRIVER_PORT) <= 0) {
  process.env.VP_TAURI_DRIVER_PORT = String(await findAvailablePort(reservedPorts))
}
if (!process.env.VP_TAURI_NATIVE_DRIVER_PORT || Number(process.env.VP_TAURI_NATIVE_DRIVER_PORT) <= 0) {
  process.env.VP_TAURI_NATIVE_DRIVER_PORT = String(await findAvailablePort(reservedPorts))
}

const run = (command, commandArgs) => {
  const result = spawnSync(command, commandArgs, {
    cwd: rootDir,
    env: withoutNetworkProxy({
      ...process.env,
      VP_E2E_CACHE_DIR: process.env.VP_E2E_CACHE_DIR ?? e2eCacheDir,
    }),
    stdio: 'inherit',
    windowsHide: true,
  })
  if (result.error) {
    throw result.error
  }
  process.exit(result.status ?? 1)
}

const ensureHiddenDesktopLauncher = () => {
  if (existsSync(launcherPath)) {
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
