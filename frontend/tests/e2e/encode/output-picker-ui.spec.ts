import { expect, test } from '../fixtures'
import { openModule } from '../utils/navigation'

test.describe('Output directory editor', () => {
  test('exposes validation and binds typed directory values', async ({ tauriPage }) => {
    await openModule(tauriPage, '编码', '编码与输出')
    const input = tauriPage.locator('input[placeholder="必填:请选择输出目录"]')
    const picker = tauriPage.locator('.panel-actions .ghost-button', { hasText: '选择输出目录' })

    await expect(input).toBeVisible()
    await expect(picker).toBeVisible()
    await input.fill('')
    await input.blur()
    await expect(input).toHaveClass(/error/)

    await input.fill('D:/vp-e2e-output')
    await input.blur()
    await expect(input).toHaveValue('D:/vp-e2e-output')
    await expect(input).not.toHaveClass(/error/)

    await input.fill('')
    await input.blur()
    await expect(input).toHaveClass(/error/)
  })
})
