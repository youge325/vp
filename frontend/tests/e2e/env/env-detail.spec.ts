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

    expect(result.result).toHaveProperty('type')
    expect(result.result).toHaveProperty('ffmpeg')
    expect(result.result).toHaveProperty('gpu')
    expect(result.result).toHaveProperty('tensorBackends')
    expect(result.result).toHaveProperty('rifeModel')

    // ffmpeg 子结构
    const ffmpeg = result.result.ffmpeg
    expect(ffmpeg).toHaveProperty('available')
    expect(typeof ffmpeg.available).toBe('boolean')
    expect(ffmpeg).toHaveProperty('version')
    expect(ffmpeg).toHaveProperty('path')
    expect(ffmpeg).toHaveProperty('ffprobePath')
    expect(ffmpeg).toHaveProperty('hwaccels')
    expect(Array.isArray(ffmpeg.hwaccels)).toBe(true)
    expect(ffmpeg).toHaveProperty('encoderProfiles')
    expect(Array.isArray(ffmpeg.encoderProfiles)).toBe(true)
    expect(ffmpeg).toHaveProperty('decoderProfiles')
    expect(Array.isArray(ffmpeg.decoderProfiles)).toBe(true)

    // gpu 子结构
    const gpu = result.result.gpu
    expect(gpu).toHaveProperty('available')
    expect(typeof gpu.available).toBe('boolean')
    expect(gpu).toHaveProperty('devices')
    expect(Array.isArray(gpu.devices)).toBe(true)
    expect(gpu).toHaveProperty('adapters')
    expect(Array.isArray(gpu.adapters)).toBe(true)

    // rife_model 子结构
    const rifeModel = result.result.rifeModel
    expect(rifeModel).toHaveProperty('available')
    expect(typeof rifeModel.available).toBe('boolean')

    // tensor_backends 子结构
    const tensorBackends = result.result.tensorBackends
    expect(tensorBackends).toHaveProperty('pytorch')
    expect(tensorBackends).toHaveProperty('paddle')
    expect(tensorBackends).toHaveProperty('onnx')

    // 可选字段 — 如果存在则验证类型
    if (result.result.resources != null) {
      expect(typeof result.result.resources).toBe('object')
    }
    if (result.result.runtime != null) {
      expect(result.result.runtime).toHaveProperty('pythonExecutable')
    }

    // ffmpeg 可用性断言（check_environment 的核心价值）
    expect(result.result.ffmpeg.available).toBe(true)
  })
})
