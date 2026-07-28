import { expect } from '../fixtures'
import type { TauriPage } from './wdio-tauri'

export async function openModule(
  tauriPage: TauriPage,
  railLabel: string,
  heading: string,
): Promise<void> {
  await tauriPage.click(`.rail-link:has-text("${railLabel}")`)
  await expect(tauriPage.locator('h2', { hasText: heading })).toBeVisible({ timeout: 5000 })
}
