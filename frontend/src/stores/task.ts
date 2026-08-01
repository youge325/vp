import { reactive, readonly, ref } from 'vue'
import { defineStore } from 'pinia'
import type { BatchEvent, ResumeConflictDescriptor } from '@/types/domain/batch'
import { createInitialBatchState, reduceBatchState } from '@/services/task/batch/state'

export const useTaskStore = defineStore('task', () => {
  const mutableBatch = reactive(createInitialBatchState())
  const batch = readonly(mutableBatch)
  const batchRuntimeIds = ref<string[]>([])
  const pendingConflict = ref<ResumeConflictDescriptor | null>(null)

  function dispatchBatch(event: BatchEvent): void {
    Object.assign(mutableBatch, reduceBatchState(mutableBatch, event))
  }

  function setRuntimeIds(ids: string[]): void {
    batchRuntimeIds.value = [...ids]
  }

  function setPendingConflict(descriptor: ResumeConflictDescriptor | null): void {
    pendingConflict.value = descriptor
  }

  return {
    batch,
    batchRuntimeIds,
    pendingConflict,
    dispatchBatch,
    setRuntimeIds,
    setPendingConflict,
  }
})
