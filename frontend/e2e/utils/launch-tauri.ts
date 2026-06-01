import { chromium, type Browser, type BrowserContext, type Page } from '@playwright/test'
import { spawn } from 'child_process'
import { Socket } from 'net'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { platform, tmpdir } from 'os'
import { mkdirSync, writeFileSync } from 'fs'

function waitForPort(port: number, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now()
    const tryConnect = () => {
      const socket = new Socket()
      socket.setTimeout(1000)
      socket.once('connect', () => {
        socket.destroy()
        resolve()
      })
      socket.once('error', () => {
        socket.destroy()
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Port ${port} not available after ${timeoutMs}ms`))
          return
        }
        setTimeout(tryConnect, 500)
      })
      socket.once('timeout', () => {
        socket.destroy()
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Port ${port} not available after ${timeoutMs}ms`))
          return
        }
        setTimeout(tryConnect, 500)
      })
      socket.connect(port, '127.0.0.1')
    }
    tryConnect()
  })
}

export async function launchTauriApp(opts: { cdpPort?: number; exePath?: string } = {}) {
  const cdpPort = opts.cdpPort ?? 9222
  const targetDir = process.env.CARGO_TARGET_DIR ?? 'src-tauri/target'
  const isWindows = platform() === 'win32'
  const defaultExeName = isWindows ? 'vp-workbench.exe' : 'vp-workbench'
  const exePath =
    opts.exePath ?? process.env.VP_TAURI_EXE_PATH ?? `${targetDir}/release/${defaultExeName}`

  // 计算项目根目录（相对于 frontend/）
  const __dirname = dirname(fileURLToPath(import.meta.url))
  const projectRoot = resolve(__dirname, '../../..')

  // 每个实例使用独立的日志目录，避免多个 Tauri 进程共享同一个日志文件
  // 导致 WinError 32（文件被占用）
  const instanceLogDir = resolve(tmpdir(), `vp-e2e-logs-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)
  mkdirSync(instanceLogDir, { recursive: true })

  const browserDebugEnv = isWindows
    ? {
        WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS:
          `--remote-debugging-port=${cdpPort} --remote-allow-origins=*`,
      }
    : { WEBKIT_INSPECTOR_SERVER: `127.0.0.1:${cdpPort}` }

  const env = {
    ...process.env,
    ...browserDebugEnv,
    VP_E2E_HEADLESS: '1',
    VP_LOG_DIR: instanceLogDir,
    // release 模式下 Tauri 需要这些环境变量来定位资源
    VP_BACKEND_DIR: resolve(projectRoot, 'backend'),
    VP_RUNTIME_ROOT: resolve(projectRoot, 'frontend/src-tauri/resources/runtime'),
    VP_FFMPEG_PATH:
      process.env.VP_FFMPEG_PATH
      ?? (isWindows ? 'D:/ffmpeg-2025-08-11-git-3542260376-full_build/bin/ffmpeg.exe' : '/usr/bin/ffmpeg'),
    VP_FFPROBE_PATH:
      process.env.VP_FFPROBE_PATH
      ?? (isWindows ? 'D:/ffmpeg-2025-08-11-git-3542260376-full_build/bin/ffprobe.exe' : '/usr/bin/ffprobe'),
    VP_RIFE_MODEL_DIR:
      process.env.VP_RIFE_MODEL_DIR ?? (isWindows ? 'D:/tmp/vp-e2e-models' : '/opt/vp/models'),
  }

  // 从 frontend/ 目录启动，确保 Tauri 的相对路径解析正确
  const cwd = resolve(__dirname, '../..')

  const proc = spawn(exePath, [], { env, cwd, detached: false })

  // 等待 webview 调试端口就绪
  await waitForPort(cdpPort, 30000)

  // Playwright attach
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${cdpPort}`)
  const context = browser.contexts()[0] ?? (await browser.newContext())
  const page = context.pages()[0] ?? (await context.newPage())

  // 等待前端加载完成
  await page.waitForSelector('[data-testid="app-shell"]', { timeout: 15000 })

  return {
    browser,
    context,
    page,
    cleanup: async () => {
      try {
        const coverage = await page.evaluate(() => (window as any).__coverage__)
        if (coverage) {
          const nycDir = resolve(projectRoot, 'frontend/.nyc_output')
          mkdirSync(nycDir, { recursive: true })
          writeFileSync(
            resolve(nycDir, `coverage-${Date.now()}.json`),
            JSON.stringify(coverage),
          )
        }
      } catch {
        // ignore — coverage not available when E2E_COVERAGE is off
      }
      try {
        await browser.close()
      } catch {
        // ignore
      }
      proc.kill('SIGKILL')
      // 等待进程（包括 Python 子进程）完全退出并释放端口/文件句柄
      await new Promise((r) => setTimeout(r, 3000))
    },
  }
}
