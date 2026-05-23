import { test, expect } from './fixtures'

test.describe('Render module UI', () => {
  test('start batch button is disabled with reason hint on fresh instance', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const startButton = tauriPage.locator('.panel-actions button.primary-button').filter({ hasText: '开始队列' })
    await expect(startButton).toBeVisible()
    await expect(startButton).toBeDisabled()

    // When disabled, a reason hint should be shown
    const reasonHint = tauriPage.locator('.start-blocked-hint')
    await expect(reasonHint).toBeVisible()
  })

  test('pause and interrupt buttons are disabled when no task is running', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const pauseButton = tauriPage.locator('.panel-actions button.ghost-button').filter({ hasText: /^(暂停队列|继续队列)$/ })
    await expect(pauseButton).toBeVisible()
    await expect(pauseButton).toBeDisabled()

    const interruptButton = tauriPage.locator('.panel-actions button.danger-button').filter({ hasText: /^(中断批次|中断中\.\.\.)$/ })
    await expect(interruptButton).toBeVisible()
    await expect(interruptButton).toBeDisabled()
  })

  test('task console renders with zero progress', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const taskConsole = tauriPage.locator('.task-console')
    await expect(taskConsole).toBeVisible()

    // Progress should show 0 / 0
    const progressLabel = taskConsole.locator('.progress-label')
    await expect(progressLabel).toBeVisible()
    await expect(progressLabel).toHaveText('0 / 0')
  })
})
