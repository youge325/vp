import { isAppBootstrapReady } from '../../e2e/utils/wdio-tauri'

describe('E2E application bootstrap readiness', () => {
  it('requires Pinia, environment completion, and persisted preset hydration', () => {
    expect(isAppBootstrapReady({
      piniaAvailable: true,
      isBootstrapping: false,
      isChecking: false,
      presetPersistenceReady: true,
    })).toBe(true)
    expect(isAppBootstrapReady({
      piniaAvailable: true,
      isBootstrapping: true,
      isChecking: false,
      presetPersistenceReady: true,
    })).toBe(false)
    expect(isAppBootstrapReady({
      piniaAvailable: false,
      isBootstrapping: false,
      isChecking: false,
      presetPersistenceReady: true,
    })).toBe(false)
    expect(isAppBootstrapReady({
      piniaAvailable: true,
      isBootstrapping: false,
      isChecking: true,
      presetPersistenceReady: true,
    })).toBe(false)
    expect(isAppBootstrapReady({
      piniaAvailable: true,
      isBootstrapping: false,
      isChecking: false,
      presetPersistenceReady: false,
    })).toBe(false)
  })
})
