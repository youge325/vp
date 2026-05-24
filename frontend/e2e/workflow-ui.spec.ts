import { test, expect } from './fixtures'

test.describe('Workflow module UI', () => {
  test('enabling interpolation reveals interpolation config panel', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    // Use `has: h2` to avoid matching the super-resolution section whose
    // "process order" option contains the substring "补帧".
    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })
    // Use .first() — panel-head may contain multiple toggles (main enable + FP16)
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    // Ensure interpolation is off before enabling (preset may have it on)
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    await toggle.click()
    await expect(toggle).toBeChecked()

    const backendSelect = section.locator('label.field').filter({ hasText: '后端' }).locator('select')
    await expect(backendSelect).toBeVisible({ timeout: 5000 })

    const algorithmSelect = section.locator('label.field').filter({ hasText: '算法' }).locator('select').first()
    await expect(algorithmSelect).toBeVisible({ timeout: 5000 })
  })

  test('enabling superResolution reveals superResolution config panel', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    // Use `has: h2` for precise section matching.
    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    // Ensure superResolution is off before enabling
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    await toggle.click()
    await expect(toggle).toBeChecked()

    const scaleSelect = section.locator('label.field').filter({ hasText: '倍率' }).locator('select').first()
    await expect(scaleSelect).toBeVisible({ timeout: 5000 })

    const algorithmSelect = section.locator('label.field').filter({ hasText: '算法' }).locator('select').first()
    await expect(algorithmSelect).toBeVisible({ timeout: 5000 })
  })

  test('enabling anime reveals anime config fields', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    // Use `has: h2` for precise section matching.
    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '动漫优化' }),
    })
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    // Ensure anime is off before enabling
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }

    await toggle.click()
    await expect(toggle).toBeChecked()

    const profileSelect = section.locator('label.field').filter({ hasText: '预设' }).locator('select')
    await expect(profileSelect).toBeVisible({ timeout: 5000 })

    const denoiseInput = section.locator('label.field').filter({ hasText: '降噪' }).locator('input')
    await expect(denoiseInput).toBeVisible({ timeout: 5000 })

    const edgeBoostInput = section.locator('label.field').filter({ hasText: '边缘增强' }).locator('input')
    await expect(edgeBoostInput).toBeVisible({ timeout: 5000 })
  })

  test('switching fpsMode swaps between targetFps input and multi select', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })

    const fpsModeSelect = section.locator('label.field').filter({ hasText: '帧率模式' }).locator('select')
    await expect(fpsModeSelect).toBeVisible()

    // The interpolation "倍率" select has options '2x' / '4x', which uniquely
    // distinguishes it from the "帧率模式" select (options '目标 FPS' / '倍率').
    const multiSelect = section.locator('label.field').filter({
      has: tauriPage.locator('option', { hasText: '2x' }),
    }).locator('select')
    const targetFpsInput = section.locator('label.field').filter({ hasText: '目标 FPS' }).locator('input')

    // Detect current mode by checking which conditional field is visible.
    const isMultiVisible = await multiSelect.isVisible().catch(() => false)

    if (isMultiVisible) {
      // Currently multi mode — switch to target
      await fpsModeSelect.selectOption({ label: '目标 FPS' })
      await expect(targetFpsInput).toBeVisible({ timeout: 5000 })
      await expect(multiSelect).not.toBeVisible()

      // Switch back to multi
      await fpsModeSelect.selectOption({ label: '倍率' })
      await expect(multiSelect).toBeVisible({ timeout: 5000 })
      await expect(targetFpsInput).not.toBeVisible()
    } else {
      // Currently target mode — switch to multi
      await fpsModeSelect.selectOption({ label: '倍率' })
      await expect(multiSelect).toBeVisible({ timeout: 5000 })
      await expect(targetFpsInput).not.toBeVisible()

      // Switch back to target
      await fpsModeSelect.selectOption({ label: '目标 FPS' })
      await expect(targetFpsInput).toBeVisible({ timeout: 5000 })
      await expect(multiSelect).not.toBeVisible()
    }
  })

  test('switching backend to onnx reveals onnx model select and hides regular model', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })

    const backendSelect = section.locator('label.field').filter({ hasText: '后端' }).locator('select')
    await expect(backendSelect).toBeVisible()

    const options = await backendSelect.locator('option').allTextContents()
    const onnxOption = options.find((o) => o.toLowerCase().includes('onnx'))
    if (!onnxOption) {
      test.skip()
      return
    }

    // Ensure we start from a non-ONNX backend so the swap is observable
    const nonOnnxOption = options.find((o) => !o.toLowerCase().includes('onnx'))
    if (nonOnnxOption) {
      await backendSelect.selectOption({ label: nonOnnxOption })
      await expect(section.locator('label.field').filter({ hasText: '模型' }).locator('select')).toBeVisible({ timeout: 5000 })
    }

    // Switch to ONNX backend
    await backendSelect.selectOption({ label: onnxOption })

    const onnxModelSelect = section.locator('label.field').filter({ hasText: 'ONNX 补帧模型' }).locator('select')
    await expect(onnxModelSelect).toBeVisible({ timeout: 5000 })

    // The regular "模型" select (label exactly "模型", not "ONNX 补帧模型")
    // is hidden by v-if="!form.isOnnxBackend". Distinguish it by checking
    // the option content — the regular model select contains options like
    // '4.25', '4.6' etc., while the ONNX model select contains '未选择'.
    const regularModelSelect = section.locator('label.field').filter({
      has: tauriPage.locator('option', { hasText: /4\.25/ }),
    }).locator('select')
    await expect(regularModelSelect).not.toBeVisible()
  })

  test('switching processOrder select updates the selected value', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })

    const processOrderSelect = section.locator('label.field').filter({ hasText: '处理顺序' }).locator('select')
    await expect(processOrderSelect).toBeVisible()

    const options = await processOrderSelect.locator('option').allTextContents()
    expect(options.length).toBeGreaterThanOrEqual(2)

    // Select the second option and verify
    await processOrderSelect.selectOption({ index: 1 })
    const selectedValue = await processOrderSelect.inputValue()
    const optionValues = await processOrderSelect.locator('option').all()
    expect(selectedValue).toBe(await optionValues[1].getAttribute('value'))

    // Switch back to first option
    await processOrderSelect.selectOption({ index: 0 })
    const newValue = await processOrderSelect.inputValue()
    expect(newValue).toBe(await optionValues[0].getAttribute('value'))
  })

  test('switching superResolution scale select updates the selected value', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })

    const scaleSelect = section.locator('label.field').filter({ hasText: '倍率' }).locator('select').first()
    await expect(scaleSelect).toBeVisible()

    const options = await scaleSelect.locator('option').allTextContents()
    if (options.length < 2) {
      test.skip()
      return
    }

    // Switch to second option
    await scaleSelect.selectOption({ index: 1 })
    const selectedValue = await scaleSelect.inputValue()
    expect(selectedValue).toBeTruthy()

    // Switch back to first option
    await scaleSelect.selectOption({ index: 0 })
    const newValue = await scaleSelect.inputValue()
    expect(newValue).toBeTruthy()
    expect(newValue).not.toBe(selectedValue)
  })

  test('switching interpolation multi select updates the selected value', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })

    // Ensure fpsMode is 'multi' so the "倍率" select is visible
    const fpsModeSelect = section.locator('label.field').filter({ hasText: '帧率模式' }).locator('select')
    await expect(fpsModeSelect).toBeVisible()
    await fpsModeSelect.selectOption({ label: '倍率' })

    const multiSelect = section.locator('label.field').filter({
      has: tauriPage.locator('option', { hasText: '2x' }),
    }).locator('select')
    await expect(multiSelect).toBeVisible({ timeout: 5000 })

    const options = await multiSelect.locator('option').allTextContents()
    if (options.length < 2) {
      test.skip()
      return
    }

    // Switch to second option
    await multiSelect.selectOption({ index: 1 })
    const selectedValue = await multiSelect.inputValue()
    expect(selectedValue).toBeTruthy()

    // Switch back to first option
    await multiSelect.selectOption({ index: 0 })
    const newValue = await multiSelect.inputValue()
    expect(newValue).toBeTruthy()
    expect(newValue).not.toBe(selectedValue)
  })
})
