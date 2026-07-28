import { expect, test } from '../fixtures'
import { saveE2EScreenshot } from '../utils/screenshots'

test.describe('Stage module UI', () => {
  test('uses the shared toggle field for both processing stages', async ({ tauriPage }) => {
    for (const stage of ['预处理', '后处理']) {
      await tauriPage.click(`.rail-link:has-text("${stage}")`)
      const toggle = tauriPage.locator('label.field.toggle-field')
        .filter({ hasText: `启用${stage}` })
        .locator('input[type="checkbox"]')
      const filterSection = tauriPage.locator('.filter-section')
      if (await toggle.isChecked()) {
        await toggle.click()
      }
      await expect(toggle).not.toBeChecked()
      await expect(filterSection).not.toBeVisible()
      await toggle.click()
      await expect(toggle).toBeChecked()
      await expect(filterSection).toBeVisible()
      await expect(filterSection.locator('.panel-caption')).toHaveCount(0)
      if (stage === '预处理') {
        await saveE2EScreenshot('toggle')
      }
    }
  })
})
