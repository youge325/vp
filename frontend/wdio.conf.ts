import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { spawnSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import net from 'node:net'
import { existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs'
import { platform, tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { resolveE2ECacheDir, rustLauncherCachePath } from './scripts/e2e-cache.mjs'
import {
  prepareE2ECoverageDirectory,
  writeE2ESessionCoverage,
} from './tests/e2e/config/coverage'
import {
  resolveE2ESpecs,
  splitSpecPatterns,
} from './tests/e2e/config/spec-groups'

const driverPort = Number(process.env.VP_TAURI_DRIVER_PORT ?? '4444')
const nativeDriverPort = Number(process.env.VP_TAURI_NATIVE_DRIVER_PORT ?? '0')
let driverProcess: ChildProcessWithoutNullStreams | undefined
const temporaryRunDirs: string[] = []

const isWindows = platform() === 'win32'
const coverageEnabled = process.env.E2E_COVERAGE === '1'
const executableName = isWindows ? 'vp-workbench.exe' : 'vp-workbench'
const cargoTargetDir = process.env.CARGO_TARGET_DIR
const defaultTargetDir = cargoTargetDir ? resolve(cargoTargetDir) : resolve(process.cwd(), 'src-tauri', 'target')
const applicationPath = process.env.VP_TAURI_EXE_PATH ?? resolve(defaultTargetDir, 'release', executableName)
const useOffscreenWindow = process.env.VP_E2E_OFFSCREEN_WINDOW === '1'
const e2eCacheDir = resolveE2ECacheDir()
const hiddenEdgeDriverSource = resolve(process.cwd(), 'tests', 'e2e', 'utils', 'hidden-msedgedriver.rs')
const hiddenEdgeDriverPath = rustLauncherCachePath(
  e2eCacheDir,
  hiddenEdgeDriverSource,
  'hidden-msedgedriver',
)
const delay = (ms: number) => new Promise<void>((resolveDelay) => setTimeout(resolveDelay, ms))
const versionPattern = /^\d+\.\d+\.\d+\.\d+$/
const cliSpecMode = process.argv.some((argument) => argument === '--spec' || argument.startsWith('--spec='))
const watchMode = process.argv.includes('--watch')
const selectedSpecPatterns = splitSpecPatterns(process.env.VP_E2E_SPECS)

const createRunDir = (label: string) => {
  const dir = resolve(tmpdir(), `vp-e2e-${label}-${process.pid}-${randomUUID()}`)
  mkdirSync(dir, { recursive: true })
  temporaryRunDirs.push(dir)
  return dir
}

const cleanupTemporaryRunDirs = async () => {
  const tempRoot = resolve(tmpdir()).toLowerCase()
  for (const dir of temporaryRunDirs.splice(0)) {
    const resolved = resolve(dir)
    if (!resolved.toLowerCase().startsWith(tempRoot)) {
      continue
    }
    let lastError: unknown
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try {
        rmSync(resolved, { recursive: true, force: true })
        lastError = undefined
        break
      } catch (error) {
        lastError = error
        await delay(300)
      }
    }
    if (lastError) {
      process.stderr.write(`Unable to remove temporary E2E directory ${resolved}: ${lastError}\n`)
    }
  }
}

const ensureHiddenEdgeDriver = () => {
  if (existsSync(hiddenEdgeDriverPath)) {
    return hiddenEdgeDriverPath
  }

  mkdirSync(dirname(hiddenEdgeDriverPath), { recursive: true })
  const result = spawnSync('rustc', [hiddenEdgeDriverSource, '-O', '-o', hiddenEdgeDriverPath], {
    stdio: 'inherit',
    windowsHide: true,
  })
  if (result.status !== 0) {
    throw new Error(`failed to build hidden EdgeDriver launcher: rustc exited with ${result.status}`)
  }
  return hiddenEdgeDriverPath
}

const compareVersions = (left: string, right: string) => {
  const leftParts = left.split('.').map(Number)
  const rightParts = right.split('.').map(Number)
  for (let index = 0; index < Math.max(leftParts.length, rightParts.length); index += 1) {
    const delta = (leftParts[index] ?? 0) - (rightParts[index] ?? 0)
    if (delta !== 0) {
      return delta
    }
  }
  return 0
}

const findInstalledWebView2Version = () => {
  const roots = [
    process.env['ProgramFiles(x86)'],
    process.env['PROGRAMFILES(X86)'],
    process.env.ProgramFiles,
    process.env.PROGRAMFILES,
    process.env.LOCALAPPDATA,
  ]

  const versions = new Set<string>()
  for (const root of roots) {
    if (!root) {
      continue
    }
    const applicationDir = resolve(root, 'Microsoft', 'EdgeWebView', 'Application')
    if (!existsSync(applicationDir)) {
      continue
    }
    for (const entry of readdirSync(applicationDir, { withFileTypes: true })) {
      if (entry.isDirectory() && versionPattern.test(entry.name)) {
        versions.add(entry.name)
      }
    }
  }

  return [...versions].sort(compareVersions).at(-1)
}

const waitForPort = async (port: number, host = '127.0.0.1', timeout = 15000) => {
  const deadline = Date.now() + timeout
  while (Date.now() <= deadline) {
    if (await canConnect(port, host)) {
      return
    }
    await delay(100)
  }
  throw new Error(`tauri-driver did not listen on ${host}:${port}`)
}

const canConnect = (port: number, host: string) => new Promise<boolean>((resolveConnect) => {
  const socket = net.connect({ port, host })
  socket.once('connect', () => {
    socket.destroy()
    resolveConnect(true)
  })
  socket.once('error', () => {
    socket.destroy()
    resolveConnect(false)
  })
})

export const config = {
  runner: 'local',
  specs: resolveE2ESpecs({
    selectedPatterns: selectedSpecPatterns,
    watchMode,
    cliSpecMode,
  }),
  exclude: [
    './tests/e2e/utils/**',
    './tests/e2e/fixtures.ts',
    ...(splitSpecPatterns(process.env.VP_E2E_EXCLUDE) ?? []),
  ],
  maxInstances: 1,
  logLevel: 'warn',
  framework: 'mocha',
  reporters: ['spec'],
  host: '127.0.0.1',
  port: driverPort,
  path: '/',
  capabilities: [
    {
      maxInstances: 1,
      'tauri:options': {
        application: applicationPath,
        args: useOffscreenWindow ? ['--vp-e2e-headless'] : [],
        ...(isWindows && useOffscreenWindow
          ? {
              webviewOptions: {
                additionalBrowserArguments: ['--window-position=-32000,-32000', '--window-size=1280,860'],
              },
            }
          : {}),
      },
    },
  ],
  mochaOpts: {
    ui: 'bdd',
    timeout: 120000,
    retries: isWindows ? 1 : 0,
  },
  autoCompileOpts: {
    autoCompile: true,
    tsNodeOpts: {
      project: './tsconfig.wdio.json',
      transpileOnly: true,
    },
  },
  onPrepare: async () => {
    prepareE2ECoverageDirectory(process.cwd(), coverageEnabled)
    if (!existsSync(applicationPath)) {
      throw new Error(`Tauri application binary was not found: ${applicationPath}`)
    }

    const appEnv = { ...process.env }
    appEnv.VP_E2E_CACHE_DIR = appEnv.VP_E2E_CACHE_DIR ?? e2eCacheDir
    appEnv.VP_APP_DATA_DIR = appEnv.VP_APP_DATA_DIR ?? createRunDir('app-data')
    appEnv.VP_LOG_DIR = appEnv.VP_LOG_DIR ?? createRunDir('logs')
    if (useOffscreenWindow) {
      appEnv.VP_E2E_HEADLESS = appEnv.VP_E2E_HEADLESS ?? '1'
      appEnv.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = [
        appEnv.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS,
        '--window-position=-32000,-32000',
        '--window-size=1280,860',
      ].filter(Boolean).join(' ')
    }

    const driverArgs = ['--port', String(driverPort)]
    if (nativeDriverPort > 0) {
      driverArgs.push('--native-port', String(nativeDriverPort))
    }
    if (isWindows) {
      const { download } = await import('edgedriver')
      const edgeDriverVersion = appEnv.VP_EDGE_DRIVER_VERSION
        ?? appEnv.EDGEDRIVER_VERSION
        ?? findInstalledWebView2Version()
      const edgeDriverCacheDir = edgeDriverVersion
        ? resolve(e2eCacheDir, 'edgedriver', edgeDriverVersion)
        : resolve(e2eCacheDir, 'edgedriver')
      appEnv.VP_EDGE_DRIVER_PATH = appEnv.VP_EDGE_DRIVER_PATH ?? await download(edgeDriverVersion, edgeDriverCacheDir)
      if (edgeDriverVersion) {
        process.stdout.write(`Using EdgeDriver for WebView2 ${edgeDriverVersion}\n`)
      }
      driverArgs.push('--native-driver', ensureHiddenEdgeDriver())
    }

    driverProcess = spawn('tauri-driver', driverArgs, {
      env: appEnv,
      stdio: 'pipe',
      windowsHide: true,
    })
    driverProcess.stdout.on('data', (chunk) => process.stdout.write(chunk))
    driverProcess.stderr.on('data', (chunk) => process.stderr.write(chunk))
    driverProcess.once('exit', (code) => {
      if (code !== null && code !== 0) {
        process.stderr.write(`tauri-driver exited with code ${code}\n`)
      }
    })

    await waitForPort(driverPort)
  },
  after: async (_result: number, _capabilities: unknown, specs: string[]) => {
    if (!coverageEnabled) {
      return
    }
    const serializedCoverage = await browser.execute(
      () => JSON.stringify((window as typeof window & { __coverage__?: unknown }).__coverage__ ?? null),
    )
    writeE2ESessionCoverage(process.cwd(), specs, serializedCoverage)
  },
  onComplete: async () => {
    const processToStop = driverProcess
    driverProcess = undefined
    if (processToStop && !processToStop.killed) {
      processToStop.kill()
      await new Promise<void>((resolveWait) => {
        const timeout = setTimeout(resolveWait, 1000)
        processToStop.once('exit', () => {
          clearTimeout(timeout)
          resolveWait()
        })
      })
    }
    await cleanupTemporaryRunDirs()
  },
}
