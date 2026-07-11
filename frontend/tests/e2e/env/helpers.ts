import type { TauriPage } from '../utils/wdio-tauri'

export async function stubNextEnvironmentRecheckClick(
  tauriPage: TauriPage,
  buttonText: string,
): Promise<boolean> {
  return await tauriPage.evaluate((text: string) => {
    const root = document.querySelector('#app')
    const vueApp = (root as any)?.__vue_app__
    const env = vueApp?.config?.globalProperties?.$pinia?.state?.value?.env?.env
    if (!env) {
      return false
    }

    const buttons = Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]
    const button = buttons.find((element) => (element.textContent ?? '').includes(text))
    if (!button) {
      return false
    }

    button.addEventListener(
      'click',
      (event) => {
        event.preventDefault()
        event.stopImmediatePropagation()

        env.isChecking = true
        env.issue = null
        env.checkResult = {
          ffmpeg: {
            available: true,
            hwaccels: [],
            encoderProfiles: [],
            decoderProfiles: [],
          },
          gpu: { adapters: [] },
          tensorEngines: {
            pytorch: [],
            paddle: [],
            onnx: [],
          },
          interpolationAlgorithms: [],
          superResolutionAlgorithms: [],
          runtimeMode: 'external',
        }
        env.checkSource = 'probe'
        env.lastProbeAt = '2026-06-30T00:00:00Z'

        window.setTimeout(() => {
          env.isChecking = false
        }, 0)
      },
      { capture: true, once: true },
    )

    return true
  }, buttonText)
}
