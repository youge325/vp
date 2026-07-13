import { test, expect } from '../fixtures'
import {
  clearResumeConflict,
  getPendingResumeConflict,
  injectResumeConflict,
} from './resume-conflict-fixture'

test.describe('Resume conflict dialog actions', () => {
  test('resume button clears pending conflict', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectResumeConflict(tauriPage, {
      kind: 'final_exists_with_resume',
      outputPath: 'C:/tmp/output.mp4',
      progress: { completedChunks: 3, completedOutputFrames: 150, totalOutputFrames: 300 },
    })
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).toBeVisible({ timeout: 5000 })

    await tauriPage.locator('button').filter({ hasText: '继续续传' }).click()
    await expect(overlay).not.toBeVisible()

    const pendingConflict = await getPendingResumeConflict(tauriPage)
    expect(pendingConflict).toBe('NULL')
  })

  test('fresh button clears pending conflict', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectResumeConflict(tauriPage, {
      kind: 'final_exists_with_resume',
      outputPath: 'C:/tmp/output.mp4',
      progress: { completedChunks: 3, completedOutputFrames: 150, totalOutputFrames: 300 },
    })
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).toBeVisible({ timeout: 5000 })

    await tauriPage.locator('button').filter({ hasText: '重新开始' }).click()
    await expect(overlay).not.toBeVisible()

    const pendingConflict = await getPendingResumeConflict(tauriPage)
    expect(pendingConflict).toBe('NULL')
  })

  test('skip button clears pending conflict', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectResumeConflict(tauriPage, {
      kind: 'final_exists_with_resume',
      outputPath: 'C:/tmp/output.mp4',
      progress: { completedChunks: 3, completedOutputFrames: 150, totalOutputFrames: 300 },
    })
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).toBeVisible({ timeout: 5000 })

    await tauriPage.locator('button').filter({ hasText: '跳过此任务' }).click()
    await expect(overlay).not.toBeVisible()

    const pendingConflict = await getPendingResumeConflict(tauriPage)
    expect(pendingConflict).toBe('NULL')
  })

  test('cancel button clears pending conflict', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectResumeConflict(tauriPage, {
      kind: 'final_exists_with_resume',
      outputPath: 'C:/tmp/output.mp4',
      progress: { completedChunks: 3, completedOutputFrames: 150, totalOutputFrames: 300 },
    })
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).toBeVisible({ timeout: 5000 })

    await tauriPage.locator('button').filter({ hasText: '取消批次' }).click()
    await expect(overlay).not.toBeVisible()

    const pendingConflict = await getPendingResumeConflict(tauriPage)
    expect(pendingConflict).toBe('NULL')
  })

  test('primary button receives initial focus in resume mode', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    const ok = await injectResumeConflict(tauriPage, {
      kind: 'final_exists_with_resume',
      outputPath: 'C:/tmp/output.mp4',
      progress: { completedChunks: 3, completedOutputFrames: 150, totalOutputFrames: 300 },
    })
    test.skip(!ok, 'Cannot access Pinia store from evaluate')

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).toBeVisible({ timeout: 5000 })

    // Primary button in resume mode is "继续续传"
    const resumeButton = tauriPage.locator('button').filter({ hasText: '继续续传' })
    const isFocused = await resumeButton.evaluate((el) => el === document.activeElement)
    expect(isFocused).toBe(true)

    // Dismiss to clean up
    await tauriPage.locator('button').filter({ hasText: '取消批次' }).click()
    await expect(overlay).not.toBeVisible()
  })

  test('dialog does not render when pendingConflict is null', async ({ tauriPage }) => {
    await tauriPage.click('.rail-link:has-text("渲染")')
    await expect(tauriPage.locator('h2:has-text("批处理队列")')).toBeVisible({ timeout: 5000 })

    await clearResumeConflict(tauriPage)

    const overlay = tauriPage.locator('.resume-conflict-overlay')
    await expect(overlay).not.toBeVisible()
  })
})
