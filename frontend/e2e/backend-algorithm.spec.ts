import { test, expect } from './fixtures'

test.describe('Backend algorithm fallback', () => {
  test('switching backend updates algorithm select options', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    // Enable interpolation section
    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    // Ensure interpolation is off before enabling
    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }
    await toggle.click()
    await expect(toggle).toBeChecked()

    // Backend select should be visible
    const backendSelect = section.locator('label.field').filter({ hasText: '后端' }).locator('select')
    await expect(backendSelect).toBeVisible({ timeout: 5000 })

    // Algorithm select should be visible
    const algorithmSelect = section.locator('label.field').filter({ hasText: '算法' }).locator('select').first()
    await expect(algorithmSelect).toBeVisible({ timeout: 5000 })

    // Algorithm options depend on env check result; skip if no algorithms available
    const initialOptions = await algorithmSelect.locator('option').allTextContents()
    if (initialOptions.length === 0) {
      test.skip()
      return
    }
    const initialAlgorithm = await algorithmSelect.inputValue()

    // Get available backend options
    const backendOptions = await backendSelect.locator('option').allTextContents()
    expect(backendOptions.length).toBeGreaterThanOrEqual(1)

    // If there's more than one backend, switch and verify algorithm options change
    if (backendOptions.length >= 2) {
      const currentValue = await backendSelect.inputValue()
      const currentBackendText = await backendSelect.locator('option').filter({ hasText: new RegExp(`^${currentValue}$`) }).textContent().catch(() => '')
      // Find a different backend option
      const otherOption = backendOptions.find((o) => o !== currentBackendText)
      if (otherOption) {
        await backendSelect.selectOption({ label: otherOption })

        // After switching, algorithm options may have changed
        const newOptions = await algorithmSelect.locator('option').allTextContents()
        const newAlgorithm = await algorithmSelect.inputValue()

        // The selected algorithm should be valid in the new backend
        expect(newOptions.length).toBeGreaterThan(0)
        expect(newOptions).toContain(await algorithmSelect.locator(`option[value="${newAlgorithm}"]`).textContent())
      }
    }
  })

  test('onnx backend reveals onnx model select for interpolation', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }
    await toggle.click()
    await expect(toggle).toBeChecked()

    const backendSelect = section.locator('label.field').filter({ hasText: '后端' }).locator('select')
    await expect(backendSelect).toBeVisible({ timeout: 5000 })

    // Check if ONNX is available
    const options = await backendSelect.locator('option').allTextContents()
    const onnxOption = options.find((o) => o.toLowerCase().includes('onnx'))
    if (!onnxOption) {
      test.skip()
      return
    }

    // Switch to ONNX
    await backendSelect.selectOption({ label: onnxOption })

    // ONNX model select should appear
    const onnxModelSelect = section.locator('label.field').filter({ hasText: 'ONNX 补帧模型' }).locator('select')
    await expect(onnxModelSelect).toBeVisible({ timeout: 5000 })
  })

  test('superResolution onnx model select appears with onnx backend', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("增强")')
    await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible({ timeout: 5000 })

    const section = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '超分' }),
    })
    const toggle = section.locator('.panel-head label.toggle-chip input[type="checkbox"]').first()
    await expect(toggle).toBeVisible()

    if (await toggle.isChecked()) {
      await toggle.click()
      await expect(toggle).not.toBeChecked()
    }
    await toggle.click()
    await expect(toggle).toBeChecked()

    // Switch backend to ONNX if available (via the interpolation section's backend)
    const interpolationSection = tauriPage.locator('section.panel-surface').filter({
      has: tauriPage.locator('h2', { hasText: '补帧' }),
    })
    const backendSelect = interpolationSection.locator('label.field').filter({ hasText: '后端' }).locator('select')
    await expect(backendSelect).toBeVisible({ timeout: 5000 })

    const options = await backendSelect.locator('option').allTextContents()
    const onnxOption = options.find((o) => o.toLowerCase().includes('onnx'))
    if (!onnxOption) {
      test.skip()
      return
    }

    await backendSelect.selectOption({ label: onnxOption })

    // In the superResolution section, ONNX model select should be visible
    const srOnnxModelSelect = section.locator('label.field').filter({ hasText: 'ONNX 超分模型' }).locator('select')
    await expect(srOnnxModelSelect).toBeVisible({ timeout: 5000 })
  })
})
