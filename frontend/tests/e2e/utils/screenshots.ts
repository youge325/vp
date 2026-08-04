import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { browser } from '@wdio/globals'

type E2EScreenshotName =
  | 'preset-banner'
  | 'environment-error'
  | 'toggle'
  | 'model-metrics'
  | 'navigation-rail'
  | 'task-running'
  | 'task-paused'
  | 'task-cancelling'
  | 'task-retry-cleared'
  | 'real-rawvsr-default'
  | 'real-rawvsr-x2'
  | 'real-rawvsr-x3'
  | 'real-rawvsr-x4'
  | 'real-rawvsr-edvr'
  | 'real-rawvsr-tdan'
  | 'real-rawvsr-toflow'

export async function saveE2EScreenshot(name: E2EScreenshotName): Promise<string | null> {
  const configuredDirectory = process.env.VP_E2E_SCREENSHOT_DIR?.trim()
  if (!configuredDirectory) {
    return null
  }

  const directory = resolve(configuredDirectory)
  mkdirSync(directory, { recursive: true })
  const outputPath = resolve(directory, `${name}.png`)
  await browser.saveScreenshot(outputPath)
  return outputPath
}
