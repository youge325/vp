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

// Phase 17 — ``setDecode / setEncode / setWorkflow / setOutput`` 4 个直接
// 替换型 setter 下线。grep 全仓 0 production callers,callsite 全部走
// ``patchX(mutator)`` 路径(可以确定性 clone + 局部修改,避免外部传入引用
// 触发 reactivity 双绑)。

export const usePresetStore = defineStore('preset', () => {
  const draftPreset = reactive<WorkbenchPreset>(createDefaultWorkbenchPreset(null))
  const presetPersistenceReady = ref(false)

  function replaceDraftPreset(next: WorkbenchPreset): void {
    draftPreset.decodeConfig = cloneDecodeConfig(next.decodeConfig)
    draftPreset.workflowConfig = cloneWorkflowConfig(next.workflowConfig)
    draftPreset.encodeConfig = cloneEncodeConfig(next.encodeConfig)
    draftPreset.outputConfig = cloneOutputConfig(next.outputConfig)
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
    patchDecode,
    patchEncode,
    patchWorkflow,
    patchOutput,
    setPersistenceReady,
  }
})
