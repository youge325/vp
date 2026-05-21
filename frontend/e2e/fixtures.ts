import { test as base, expect } from '@playwright/test'
import { launchTauriApp } from './utils/launch-tauri'

export { expect }

export const test = base.extend<{
  tauriPage: import('@playwright/test').Page
}>({
  tauriPage: async ({}, use) => {
    const { page, cleanup } = await launchTauriApp()
    await use(page)
    await cleanup()
  },
})
