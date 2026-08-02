import { expect, test } from '../fixtures'
import {
  setDeterministicEnhanceMetricState,
  setDeterministicRealRawVsrState,
} from '../utils/pinia'
import { saveE2EScreenshot } from '../utils/screenshots'
import type { TauriPage } from '../utils/wdio-tauri'

async function openWorkflow(tauriPage: TauriPage) {
  await tauriPage.click('.rail-link:has-text("增强")')
  await expect(tauriPage.locator('h2:has-text("增强流程")')).toBeVisible()
}

const workflowSection = (tauriPage: TauriPage, heading: string) =>
  tauriPage.locator('section.panel-surface').filter({
    has: tauriPage.locator('h2', { hasText: heading }),
  })

test.describe('Workflow module UI', () => {
  test('enables both stages and reveals their bound controls', async ({ tauriPage }) => {
    await openWorkflow(tauriPage)
    for (const stage of [
      { heading: '补帧', field: '后端' },
      { heading: '超分', field: '倍率' },
    ]) {
      const section = workflowSection(tauriPage, stage.heading)
      const toggle = section.locator('.panel-head input[type="checkbox"]').first()
      if (await toggle.isChecked()) {
        await toggle.click()
      }
      await toggle.click()
      await expect(toggle).toBeChecked()
      await expect(section.locator('label.field').filter({
        hasText: stage.field,
      }).locator('select').first()).toBeVisible()
      await expect(section.locator('label.field').filter({
        hasText: '算法',
      }).locator('select').first()).toBeVisible()
    }
  })

  test('renders all model projections through the shared metric grid', async ({ tauriPage }) => {
    const ready = await setDeterministicEnhanceMetricState()
    test.skip(!ready, 'Cannot seed deterministic model metrics')
    await openWorkflow(tauriPage)

    const interpolation = tauriPage.locator(
      '.model-metric-grid[aria-label="补帧模型指标"]',
    )
    const superResolution = tauriPage.locator(
      '.model-metric-grid[aria-label="超分模型指标"]',
    )
    const combined = tauriPage.locator(
      '.model-metric-grid[aria-label="增强流程组合显存峰值"]',
    )
    await expect(tauriPage.locator('.model-metric-grid')).toHaveCount(3)
    await expect(interpolation.locator('.model-metric-item')).toHaveCount(3)
    await expect(superResolution.locator('.model-metric-item')).toHaveCount(3)
    await expect(combined.locator('.model-metric-item')).toHaveCount(1)
    await expect(interpolation).toContainText('1.25M')
    await expect(superResolution).toContainText('7.50M')
    await expect(combined).toContainText('组合峰值')
    await superResolution.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    await saveE2EScreenshot('model-metrics')
  })

  test('switches between target FPS and interpolation multiplier inputs', async ({ tauriPage }) => {
    await openWorkflow(tauriPage)
    const section = workflowSection(tauriPage, '补帧')
    const mode = section.locator('label.field').filter({ hasText: '帧率模式' }).locator('select')
    const target = section.locator('label.field').filter({ hasText: '目标 FPS' }).locator('input')
    const multiplier = section.locator('label.field').filter({
      has: tauriPage.locator('option', { hasText: '2x' }),
    }).locator('select')

    await mode.selectOption({ label: '倍率' })
    await expect(multiplier).toBeVisible()
    await expect(target).not.toBeVisible()
    const choices = await multiplier.locator('option').allTextContents()
    if (choices.length > 1) {
      await multiplier.selectOption({ index: 1 })
      expect(await multiplier.inputValue()).toBeTruthy()
    }

    await mode.selectOption({ label: '目标 FPS' })
    await expect(target).toBeVisible()
    await expect(multiplier).not.toBeVisible()
  })

  test('switches ONNX backend to its dedicated model selector', async ({ tauriPage }) => {
    await openWorkflow(tauriPage)
    const section = workflowSection(tauriPage, '补帧')
    const backend = section.locator('label.field').filter({ hasText: '后端' }).locator('select')
    const choices = await backend.locator('option').allTextContents()
    const onnx = choices.find((choice) => choice.toLowerCase().includes('onnx'))
    test.skip(!onnx, 'ONNX interpolation backend is unavailable')
    await backend.selectOption({ label: onnx! })

    const onnxModel = section.locator('label.field')
      .filter({ hasText: 'ONNX 补帧模型' })
      .locator('select')
    await expect(onnxModel).toBeVisible()
    await expect(section.locator('label.field').filter({ hasText: /^模型$/ })).not.toBeVisible()
  })

  test('binds process order and super-resolution scale choices', async ({ tauriPage }) => {
    await openWorkflow(tauriPage)
    const section = workflowSection(tauriPage, '超分')
    for (const label of ['处理顺序', '倍率']) {
      const select = section.locator('label.field').filter({ hasText: label }).locator('select').first()
      const options = await select.locator('option').all()
      test.skip(options.length < 2, `${label} has fewer than two choices`)
      await select.selectOption({ index: 1 })
      expect(await select.inputValue()).toBe(await options[1].getAttribute('value'))
    }
  })

  test('renders Real-RawVSR license and all three scale-specific metrics', async ({ tauriPage }) => {
    const ready = await setDeterministicRealRawVsrState()
    test.skip(!ready, 'Cannot seed deterministic Real-RawVSR state')
    await openWorkflow(tauriPage)

    const section = workflowSection(tauriPage, '超分')
    const algorithm = section.locator('label.field').filter({ hasText: '算法' }).locator('select')
    expect((await algorithm.locator('option').allTextContents()).length).toBe(4)
    const scale = section.locator('label.field').filter({ hasText: '倍率' }).locator('select')
    await expect(scale.locator('option')).toHaveCount(3)
    expect(await scale.locator('option').allTextContents()).toEqual(['2x', '3x', '4x'])
    const license = tauriPage.locator('.model-license-banner')
    await expect(license).toContainText('仅限非商业研究与个人使用')
    await expect(license).toContainText('CC-BY-NC-SA-4.0')
    await license.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    await saveE2EScreenshot('real-rawvsr-default')

    const parameterLabels = { 2: '6.14M', 3: '6.33M', 4: '6.29M' } as const
    for (const factor of [2, 3, 4] as const) {
      await scale.selectOption(String(factor))
      await expect(scale).toHaveValue(String(factor))
      await expect(tauriPage.locator('.model-metric-grid[aria-label="超分模型指标"]')).toContainText(
        parameterLabels[factor],
      )
      await saveE2EScreenshot(`real-rawvsr-x${factor}`)
    }

    for (const [algorithmId, label, screenshot] of [
      ['real-rawvsr-edvr', 'Real-RawVSR EDVR', 'real-rawvsr-edvr'],
      ['real-rawvsr-tdan', 'Real-RawVSR TDAN', 'real-rawvsr-tdan'],
      ['real-rawvsr-toflow', 'Real-RawVSR TOFlow', 'real-rawvsr-toflow'],
    ] as const) {
      await algorithm.selectOption(algorithmId)
      await expect(algorithm).toHaveValue(algorithmId)
      await expect(license).toContainText(label)
      await expect(tauriPage.locator('.model-metric-grid[aria-label="超分固定窗口"]')).toContainText(
        '5 帧（固定）',
      )
      await saveE2EScreenshot(screenshot)
    }
  })
})
