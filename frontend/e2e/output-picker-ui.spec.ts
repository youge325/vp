import { test, expect } from './fixtures'

async function injectOutputDir(tauriPage: any, outputDir: string): Promise<boolean> {
  return await tauriPage.evaluate((dir: string) => {
    const root = document.querySelector('#app')
    if (!root) return false
    const vueApp = (root as any).__vue_app__
    if (!vueApp) return false
    const pinia = vueApp.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.preset?.draftPreset?.outputConfig) return false

    pinia.state.value.preset.draftPreset.outputConfig.outputDir = dir
    return true
  }, outputDir)
}

test.describe('Output picker UI', () => {
  test('output directory button exists in encode module', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const button = tauriPage.locator('.panel-actions .ghost-button')
    await expect(button).toBeVisible()
    await expect(button).toHaveText('选择输出目录')
    await expect(button).toBeEnabled()
  })

  test('output directory input shows empty-state with error class', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    // Ensure outputDir is empty for this test
    const cleared = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset?.outputConfig) return false
      pinia.state.value.preset.draftPreset.outputConfig.outputDir = ''
      return true
    })
    test.skip(!cleared, 'Cannot access Pinia preset store from evaluate')

    const input = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')
    await expect(input).toHaveValue('')
    await expect(input).toHaveClass(/input-error/)

    // BaseField should show the error message
    const fieldError = tauriPage.locator('.field-error')
    await expect(fieldError).toBeVisible()
    await expect(fieldError).toContainText('必填:请选择或填写输出目录')
  })

  test('setting outputDir via store injection updates input and removes error state', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const input = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')

    // Ensure outputDir is empty so the input-error class is present
    const cleared = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset?.outputConfig) return false
      pinia.state.value.preset.draftPreset.outputConfig.outputDir = ''
      return true
    })
    test.skip(!cleared, 'Cannot access Pinia preset store from evaluate')
    await expect(input).toHaveClass(/input-error/)

    const ok = await injectOutputDir(tauriPage, 'C:/test/output')
    test.skip(!ok, 'Cannot access Pinia preset store from evaluate')

    // Wait for Vue reactivity to update the DOM
    await expect(input).toHaveValue('C:/test/output')
    await expect(input).not.toHaveClass(/input-error/)
    await expect(tauriPage.locator('.field-error')).not.toBeVisible()
  })

  test('clearing outputDir restores error state', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const input = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')

    // First set a valid path
    const ok = await injectOutputDir(tauriPage, 'C:/test/output')
    test.skip(!ok, 'Cannot access Pinia preset store from evaluate')
    await expect(input).toHaveValue('C:/test/output')
    await expect(input).not.toHaveClass(/input-error/)

    // Then clear it
    const cleared = await injectOutputDir(tauriPage, '')
    test.skip(!cleared, 'Cannot access Pinia preset store from evaluate')
    await expect(input).toHaveValue('')
    await expect(input).toHaveClass(/input-error/)
    await expect(tauriPage.locator('.field-error')).toBeVisible()
  })

  test('typing into outputDir input updates the value', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("编码")')
    await expect(tauriPage.locator('h2:has-text("编码与输出")')).toBeVisible({ timeout: 5000 })

    const input = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')

    // Ensure it starts empty so we can type
    const ok = await tauriPage.evaluate(() => {
      const root = document.querySelector('#app')
      if (!root) return false
      const vueApp = (root as any).__vue_app__
      if (!vueApp) return false
      const pinia = vueApp.config?.globalProperties?.$pinia
      if (!pinia?.state?.value?.preset?.draftPreset?.outputConfig) return false
      pinia.state.value.preset.draftPreset.outputConfig.outputDir = ''
      return true
    })
    test.skip(!ok, 'Cannot access Pinia preset store from evaluate')
    await expect(input).toHaveValue('')

    // Type a path and blur
    await input.fill('D:/videos/export')
    await input.blur()

    // The input should retain the typed value
    await expect(input).toHaveValue('D:/videos/export')
    await expect(input).not.toHaveClass(/input-error/)
  })
})
