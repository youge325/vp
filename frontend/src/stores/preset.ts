import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  loadWorkbenchPreset as invokeLoadWorkbenchPreset,
  saveWorkbenchPreset as invokeSaveWorkbenchPreset,
  pickOutputDirectory as invokePickOutputDirectory,
} from '@/lib/tauri'
import {
  cloneDecodeConfig,
  cloneEncodeConfig,
  cloneOutputConfig,
  cloneWorkflowConfig,
  cloneWorkbenchPreset,
  createDefaultWorkbenchPreset,
  getVisibleDecoderProfiles,
  getVisibleEncoderProfiles,
  normalizeTaskError,
} from '@/lib/task-mapper'
import {
  defaultRateControlValue,
  inferHwaccelForProfile,
  normalizeDecodeConfig as normalizeDecode,
  normalizeEncodeConfig as normalizeEncode,
  seedProfileOptions,
} from '@/services/config'
import { useEnvStore } from '@/stores/env'
import type {
  CapabilityValue,
  DecodeConfig,
  EncodeConfig,
  EnvironmentCheckResult,
  WorkbenchPreset,
} from '@/types'

const PRESET_SAVE_DEBOUNCE_MS = 300

function coercePreset(raw: WorkbenchPreset | null, env: EnvironmentCheckResult | null): WorkbenchPreset {
  const defaults = createDefaultWorkbenchPreset(env)
  if (!raw) {
    return defaults
  }

  return {
    decodeConfig: raw.decodeConfig ? cloneDecodeConfig(raw.decodeConfig) : defaults.decodeConfig,
    workflowConfig: raw.workflowConfig ? cloneWorkflowConfig(raw.workflowConfig) : defaults.workflowConfig,
    encodeConfig: raw.encodeConfig ? cloneEncodeConfig(raw.encodeConfig) : defaults.encodeConfig,
    outputConfig: raw.outputConfig ? cloneOutputConfig(raw.outputConfig) : defaults.outputConfig,
  }
}

export const usePresetStore = defineStore('preset', () => {
  const envStore = useEnvStore()

  const draftPreset = reactive<WorkbenchPreset>(createDefaultWorkbenchPreset(null))
  let presetSaveTimer: ReturnType<typeof setTimeout> | null = null
  const presetPersistenceReady = ref(false)

  const currentEncoderProfile = computed(() => {
    const profiles = getVisibleEncoderProfiles(envStore.env.checkResult)
    return (
      profiles.find((profile) => profile.name === draftPreset.encodeConfig.codec) ??
      profiles[0] ??
      null
    )
  })

  const currentDecoderProfile = computed(() => {
    const visibleProfiles = getVisibleDecoderProfiles(envStore.env.checkResult, '')
    const selectedName = draftPreset.decodeConfig.mode === 'software' ? 'software' : draftPreset.decodeConfig.decoder
    return (
      visibleProfiles.find((profile) => profile.name === selectedName) ??
      visibleProfiles[0] ??
      null
    )
  })

  function replaceDraftPreset(next: WorkbenchPreset): void {
    draftPreset.decodeConfig = cloneDecodeConfig(next.decodeConfig)
    draftPreset.workflowConfig = cloneWorkflowConfig(next.workflowConfig)
    draftPreset.encodeConfig = cloneEncodeConfig(next.encodeConfig)
    draftPreset.outputConfig = cloneOutputConfig(next.outputConfig)
  }

  function schedulePresetSave(): void {
    if (!presetPersistenceReady.value) {
      return
    }
    if (presetSaveTimer) {
      clearTimeout(presetSaveTimer)
    }
    presetSaveTimer = setTimeout(() => {
      presetSaveTimer = null
      void persistWorkbenchPreset()
    }, PRESET_SAVE_DEBOUNCE_MS)
  }

  async function persistWorkbenchPreset(): Promise<void> {
    try {
      await invokeSaveWorkbenchPreset(cloneWorkbenchPreset(draftPreset))
    } catch {
      // Ignore persistence failures and keep the in-memory editor usable.
    }
  }

  async function loadPersistedPreset(): Promise<boolean> {
    try {
      const preset = await invokeLoadWorkbenchPreset()
      if (!preset) {
        replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
        return false
      }
      replaceDraftPreset(coercePreset(preset, envStore.env.checkResult))
      return true
    } catch {
      replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
      return false
    }
  }

  function normalizeDecodeConfig(
    config: DecodeConfig,
    videoCodec: string,
    preferDefaults = false,
  ): DecodeConfig {
    return normalizeDecode(config, envStore.env.checkResult, videoCodec, preferDefaults)
  }

  function normalizeEncodeConfig(config: EncodeConfig, preferDefaults = false): EncodeConfig {
    return normalizeEncode(config, envStore.env.checkResult, preferDefaults)
  }

  function normalizeDraftPresetProfiles(preferDefaults = false): void {
    draftPreset.decodeConfig = normalizeDecodeConfig(draftPreset.decodeConfig, '', preferDefaults)
    draftPreset.encodeConfig = normalizeEncodeConfig(draftPreset.encodeConfig, preferDefaults)
  }

  function patchWorkflow(mutator: (config: WorkbenchPreset['workflowConfig']) => void): void {
    const nextDraft = cloneWorkflowConfig(draftPreset.workflowConfig)
    mutator(nextDraft)
    draftPreset.workflowConfig = nextDraft
    schedulePresetSave()
  }

  function patchDecode(mutator: (config: DecodeConfig) => void): void {
    const nextDraft = cloneDecodeConfig(draftPreset.decodeConfig)
    mutator(nextDraft)
    draftPreset.decodeConfig = nextDraft
    normalizeDraftPresetProfiles()
    schedulePresetSave()
  }

  function patchEncode(mutator: (config: EncodeConfig) => void): void {
    const nextDraft = cloneEncodeConfig(draftPreset.encodeConfig)
    mutator(nextDraft)
    draftPreset.encodeConfig = nextDraft
    normalizeDraftPresetProfiles()
    schedulePresetSave()
  }

  function patchOutput(mutator: (config: WorkbenchPreset['outputConfig']) => void): void {
    const nextDraft = cloneOutputConfig(draftPreset.outputConfig)
    mutator(nextDraft)
    draftPreset.outputConfig = nextDraft
    schedulePresetSave()
  }

  function setDecodeProfile(profileName: string): void {
    const allProfiles = getVisibleDecoderProfiles(envStore.env.checkResult, '')
    const profile = allProfiles.find((entry) => entry.name === profileName) ?? null
    patchDecode((config) => {
      if (!profile || profile.family === 'software') {
        config.mode = 'software'
        config.hwaccel = ''
        config.hwaccelDevice = ''
        config.decoder = 'software'
        config.options = {}
        return
      }

      config.mode = 'hardware'
      config.hwaccel = inferHwaccelForProfile(profile)
      config.decoder = profile.name
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setDecodeHwaccelDevice(value: string): void {
    patchDecode((config) => {
      config.hwaccelDevice = value
    })
  }

  function setDecodeOption(optionName: string, value: CapabilityValue): void {
    patchDecode((config) => {
      config.options = { ...config.options, [optionName]: value }
    })
  }

  function setEncodeProfile(profileName: string): void {
    const profiles = getVisibleEncoderProfiles(envStore.env.checkResult)
    const profile = profiles.find((entry) => entry.name === profileName) ?? null
    if (!profile) {
      return
    }

    patchEncode((config) => {
      config.codec = profile.name
      config.family =
        profile.family === 'nvidia' || profile.family === 'intel' ? profile.family : 'cpu'
      config.rateControl = defaultRateControlValue(
        profile.family === 'nvidia' || profile.family === 'intel' ? profile.family : 'cpu',
      )
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setEncodeRateControlMode(mode: EncodeConfig['rateControl']['mode']): void {
    patchEncode((config) => {
      config.rateControl = { mode, value: config.rateControl.value }
    })
  }

  function setEncodeRateControlValue(value: number): void {
    patchEncode((config) => {
      config.rateControl = { ...config.rateControl, value }
    })
  }

  function setEncodeOption(optionName: string, value: CapabilityValue): void {
    patchEncode((config) => {
      config.options = { ...config.options, [optionName]: value }
    })
  }

  async function pickOutputDirectory(): Promise<{ outputDir: string | null; error: import('@/types').TaskError | null }> {
    try {
      const outputDir = await invokePickOutputDirectory()
      if (outputDir) {
        patchOutput((config) => {
          config.outputDir = outputDir
        })
      }
      return { outputDir, error: null }
    } catch (error) {
      return { outputDir: null, error: normalizeTaskError(error, 'pick_output_dir_failed') }
    }
  }

  function getOptionValue(
    option: { name: string; defaultValue?: CapabilityValue | null; choices: Array<{ value: CapabilityValue }>; type: string },
    values: Record<string, CapabilityValue>,
  ): CapabilityValue {
    if (option.name in values) {
      return values[option.name] as CapabilityValue
    }
    if (option.defaultValue != null) {
      return option.defaultValue
    }
    if (option.type === 'boolean') {
      return false
    }
    if (option.choices.length > 0) {
      return option.choices[0]?.value ?? ''
    }
    return ''
  }

  return {
    draftPreset,
    presetPersistenceReady,
    currentEncoderProfile,
    currentDecoderProfile,
    replaceDraftPreset,
    schedulePresetSave,
    persistWorkbenchPreset,
    loadPersistedPreset,
    normalizeDecodeConfig,
    normalizeEncodeConfig,
    normalizeDraftPresetProfiles,
    patchWorkflow,
    patchDecode,
    patchEncode,
    patchOutput,
    setDecodeProfile,
    setDecodeHwaccelDevice,
    setDecodeOption,
    setEncodeProfile,
    setEncodeRateControlMode,
    setEncodeRateControlValue,
    setEncodeOption,
    pickOutputDirectory,
    getOptionValue,
  }
})
