import { expect, test } from '../fixtures'
import { seedMediaItems } from '../utils/media'
import { openModule } from '../utils/navigation'
import type { TauriPage } from '../utils/wdio-tauri'

const outputInput = (tauriPage: TauriPage) =>
  tauriPage.locator('input[placeholder="必填:请选择输出目录"]')

test.describe('Preset and media editor isolation', () => {
  test('keeps preset and active-item output directories independent through the UI', async ({ tauriPage }) => {
    await seedMediaItems([])
    await openModule(tauriPage, '编码', '编码与输出')
    const presetInput = outputInput(tauriPage)
    await presetInput.fill('D:/preset-only')
    await presetInput.blur()
    await expect(presetInput).toHaveValue('D:/preset-only')

    const ready = await seedMediaItems([{
      id: 'isolated-item',
      displayName: 'isolated.mp4',
      outputDir: 'D:/item-only',
    }])
    test.skip(!ready, 'Cannot seed media fixture')
    await expect(outputInput(tauriPage)).toHaveValue('D:/item-only')

    const itemInput = outputInput(tauriPage)
    await itemInput.fill('D:/item-edited')
    await itemInput.blur()
    await expect(itemInput).toHaveValue('D:/item-edited')

    await seedMediaItems([])
    await expect(outputInput(tauriPage)).toHaveValue('D:/preset-only')
  })
})
