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
          type: 'check',
          ffmpeg: {
            available: true,
            version: 'e2e-stub',
            path: 'ffmpeg',
            ffprobePath: 'ffprobe',
            hwaccels: [],
            encoderProfiles: [],
            decoderProfiles: [],
          },
          gpu: {
            available: false,
            devices: [],
            adapters: [],
            cudaAvailable: false,
          },
          tensorBackends: {
            pytorch: false,
            paddle: false,
            onnx: true,
          },
          tensorEngines: {
            pytorch: [],
            paddle: [],
            onnx: [],
          },
          backendDeviceSupport: {
            pytorch: ['nvidia', 'intel', 'amd'],
            paddle: ['nvidia', 'intel', 'amd', 'hygon'],
            onnx: ['nvidia', 'intel', 'amd'],
          },
          onnxRuntime: {
            available: true,
            providers: [],
          },
          rifeModel: {
            available: true,
            version: '4.25',
            path: 'rife_v4.25.onnx',
          },
          interpolationAlgorithms: [],
          superResolutionAlgorithms: [],
          animeProfiles: [],
          runtime: {
            mode: 'e2e',
            bundled: true,
            pythonExecutable: 'python',
            defaultModelAvailable: true,
          },
          resources: {},
        }
        env.checkSource = 'probe'
        env.lastCheckedAt = new Date().toISOString()
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
