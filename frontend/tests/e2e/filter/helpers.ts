import { expect } from '../fixtures'
import { openModule } from '../utils/navigation'
import type { LocatorAdapter, TauriPage } from '../utils/wdio-tauri'

export async function openEmptyFilterSection(
  tauriPage: TauriPage,
  stage: '预处理' | '后处理' = '预处理',
): Promise<LocatorAdapter> {
  await openModule(tauriPage, stage, stage)
  const section = tauriPage.locator('section.panel-surface').filter({
    has: tauriPage.locator('h2', { hasText: stage }),
  })
  const toggle = section.locator('label.field.toggle-field input[type="checkbox"]').first()
  await expect(toggle).toBeVisible()
  if (!(await toggle.isChecked())) {
    await toggle.click()
  }
  await expect(toggle).toBeChecked()

  const cards = section.locator('.filter-card')
  while ((await cards.count()) > 0) {
    await cards.first().locator('.filter-delete').click()
  }
  await expect(section.locator('.filter-empty')).toBeVisible()
  return section
}

export async function addFilter(
  section: LocatorAdapter,
  label: string,
): Promise<LocatorAdapter> {
  await section.locator('.filter-toolbar select').selectOption({ label })
  const card = section.locator('.filter-card').filter({ hasText: label }).last()
  await expect(card.locator('.filter-kind')).toHaveText(label)
  return card
}
