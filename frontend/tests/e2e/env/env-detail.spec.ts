import { test, expect } from '../fixtures'

test.describe('Environment detail', () => {
  test('check_environment result contains all core schema sections', async ({ tauriPage }) => {
    const result = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error
        return await window.__TAURI_INTERNALS__.invoke('check_environment', { forceRefresh: false })
      } catch (error: any) {
        throw new Error(`check_environment failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    expect(Object.keys(result.result).sort()).toEqual([
      'backendDeviceSupport',
      'ffmpeg',
      'gpu',
      'interpolationAlgorithms',
      'runtimeMode',
      'superResolutionAlgorithms',
      'tensorEngines',
    ])

    // ffmpeg 子结构
    const ffmpeg = result.result.ffmpeg
    expect(Object.keys(ffmpeg).sort()).toEqual(['available', 'decoderProfiles', 'encoderProfiles', 'hwaccels'])
    expect(typeof ffmpeg.available).toBe('boolean')
    expect(Array.isArray(ffmpeg.hwaccels)).toBe(true)
    expect(Array.isArray(ffmpeg.encoderProfiles)).toBe(true)
    expect(Array.isArray(ffmpeg.decoderProfiles)).toBe(true)

    // gpu 子结构
    const gpu = result.result.gpu
    expect(Object.keys(gpu)).toEqual(['adapters'])
    expect(Array.isArray(gpu.adapters)).toBe(true)

    for (const matrix of [result.result.tensorEngines, result.result.backendDeviceSupport]) {
      expect(Object.keys(matrix).sort()).toEqual(['onnx', 'paddle', 'pytorch'])
      expect(Array.isArray(matrix.pytorch)).toBe(true)
      expect(Array.isArray(matrix.paddle)).toBe(true)
      expect(Array.isArray(matrix.onnx)).toBe(true)
    }

    expect(Array.isArray(result.result.interpolationAlgorithms)).toBe(true)
    expect(Array.isArray(result.result.superResolutionAlgorithms)).toBe(true)
    expect(typeof result.result.runtimeMode).toBe('string')
    expect(result.result.ffmpeg.available).toBe(true)
  })
})
