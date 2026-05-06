import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset, WorkflowConfig } from '@/types/protocol'
import {
  cloneDecodeConfig,
  cloneEncodeConfig,
  cloneOutputConfig,
  cloneWorkflowConfig,
} from '@/services/preset/clone'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'

export const usePresetStore = defineStore('preset', () => {
  const draftPreset = reactive<WorkbenchPreset>(createDefaultWorkbenchPreset(null))
  const presetPersistenceReady = ref(false)

  function replaceDraftPreset(next: WorkbenchPreset): void {
    draftPreset.decodeConfig = cloneDecodeConfig(next.decodeConfig)
    draftPreset.workflowConfig = cloneWorkflowConfig(next.workflowConfig)
    draftPreset.encodeConfig = cloneEncodeConfig(next.encodeConfig)
    draftPreset.outputConfig = cloneOutputConfig(next.outputConfig)
  }

  function setDecode(next: DecodeConfig): void {
    draftPreset.decodeConfig = next
  }

  function setEncode(next: EncodeConfig): void {
    draftPreset.encodeConfig = next
  }

  function setWorkflow(next: WorkflowConfig): void {
    draftPreset.workflowConfig = next
  }

  function setOutput(next: OutputConfig): void {
    draftPreset.outputConfig = next
  }

  function patchDecode(mutator: (config: DecodeConfig) => void): void {
    const next = cloneDecodeConfig(draftPreset.decodeConfig)
    mutator(next)
    draftPreset.decodeConfig = next
  }

  function patchEncode(mutator: (config: EncodeConfig) => void): void {
    const next = cloneEncodeConfig(draftPreset.encodeConfig)
    mutator(next)
    draftPreset.encodeConfig = next
  }

  function patchWorkflow(mutator: (config: WorkflowConfig) => void): void {
    const next = cloneWorkflowConfig(draftPreset.workflowConfig)
    mutator(next)
    draftPreset.workflowConfig = next
  }

  function patchOutput(mutator: (config: OutputConfig) => void): void {
    const next = cloneOutputConfig(draftPreset.outputConfig)
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
    setDecode,
    setEncode,
    setWorkflow,
    setOutput,
    patchDecode,
    patchEncode,
    patchWorkflow,
    patchOutput,
    setPersistenceReady,
  }
})
