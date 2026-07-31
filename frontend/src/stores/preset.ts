import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset, WorkflowConfig } from '@/types/protocol'
import { clonePresetData } from '@/services/preset/clone'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'

export const usePresetStore = defineStore('preset', () => {
  const draftPreset = reactive<WorkbenchPreset>(createDefaultWorkbenchPreset(null))
  const presetPersistenceReady = ref(false)

  function replaceDraftPreset(next: WorkbenchPreset): void {
    draftPreset.decodeConfig = clonePresetData(next.decodeConfig)
    draftPreset.workflowConfig = clonePresetData(next.workflowConfig)
    draftPreset.encodeConfig = clonePresetData(next.encodeConfig)
    draftPreset.outputConfig = clonePresetData(next.outputConfig)
  }

  function patchDecode(mutator: (config: DecodeConfig) => void): void {
    const next = clonePresetData(draftPreset.decodeConfig)
    mutator(next)
    draftPreset.decodeConfig = next
  }

  function patchEncode(mutator: (config: EncodeConfig) => void): void {
    const next = clonePresetData(draftPreset.encodeConfig)
    mutator(next)
    draftPreset.encodeConfig = next
  }

  function patchWorkflow(mutator: (config: WorkflowConfig) => void): void {
    const next = clonePresetData(draftPreset.workflowConfig)
    mutator(next)
    draftPreset.workflowConfig = next
  }

  function patchOutput(mutator: (config: OutputConfig) => void): void {
    const next = clonePresetData(draftPreset.outputConfig)
    mutator(next)
    draftPreset.outputConfig = next
  }

  function setPersistenceReady(value: boolean): void {
    presetPersistenceReady.value = value
  }

  return {
    draftPreset,
    presetPersistenceReady,
    replaceDraftPreset,
    patchDecode,
    patchEncode,
    patchWorkflow,
    patchOutput,
    setPersistenceReady,
  }
})
