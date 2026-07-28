import type { ResumeConflictDescriptor } from '@/types/domain/batch'
import type { TauriPage } from '../utils/wdio-tauri'

export async function injectResumeConflict(
  tauriPage: TauriPage,
  descriptor: ResumeConflictDescriptor,
): Promise<boolean> {
  return await tauriPage.evaluate((conflict) => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    const pinia = vueApp?.config?.globalProperties?.$pinia
    if (!pinia?.state?.value?.task) {
      return false
    }
    pinia.state.value.task.pendingConflict = conflict
    return true
  }, descriptor)
}

export async function clearResumeConflict(tauriPage: TauriPage): Promise<void> {
  await tauriPage.evaluate(() => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    const pinia = vueApp?.config?.globalProperties?.$pinia
    if (pinia?.state?.value?.task) {
      pinia.state.value.task.pendingConflict = null
    }
  })
}
