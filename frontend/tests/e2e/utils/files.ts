import { existsSync, rmSync, statSync } from 'node:fs'

const E2E_FILE_POLL_INTERVAL_MS = 100

const delay = () => new Promise<void>((resolveDelay) => {
  setTimeout(resolveDelay, E2E_FILE_POLL_INTERVAL_MS)
})

export async function waitForNonEmptyFile(outputPath: string, maxWaitMs = 60000): Promise<boolean> {
  const deadline = Date.now() + maxWaitMs
  while (Date.now() <= deadline) {
    if (existsSync(outputPath) && statSync(outputPath).size > 0) {
      return true
    }
    await delay()
  }
  return false
}

export async function removeFileWhenUnlocked(outputPath: string, maxWaitMs = 15000): Promise<void> {
  const deadline = Date.now() + maxWaitMs
  let lastError: unknown

  while (Date.now() <= deadline) {
    if (!existsSync(outputPath)) {
      return
    }
    try {
      rmSync(outputPath)
      return
    } catch (error) {
      lastError = error
      await delay()
    }
  }

  throw lastError
}
