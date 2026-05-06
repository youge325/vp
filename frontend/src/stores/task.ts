import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type { BatchState, ResumeConflictDescriptor } from '@/types/domain/batch'

function createInitialBatch(): BatchState {
  return {
    queue: [],
    currentId: null,
    completedCount: 0,
    failedCount: 0,
    isRunning: false,
    isPaused: false,
    isCancelling: false,
  }
}

export const useTaskStore = defineStore('task', () => {
  const batch = reactive<BatchState>(createInitialBatch())
  const batchRuntimeIds = ref<string[]>([])
  const pendingConflict = ref<ResumeConflictDescriptor | null>(null)

  function setBatch(partial: Partial<BatchState>): void {
    Object.assign(batch, partial)
  }

  function setRuntimeIds(ids: string[]): void {
    batchRuntimeIds.value = [...ids]
  }

  function setPendingConflict(descriptor: ResumeConflictDescriptor | null): void {
    pendingConflict.value = descriptor
  }

  function resetBatch(): void {
    Object.assign(batch, createInitialBatch())
    batchRuntimeIds.value = []
    pendingConflict.value = null
  }

  return {
    batch,
    batchRuntimeIds,
    pendingConflict,
    setBatch,
    setRuntimeIds,
    setPendingConflict,
    resetBatch,
  }
})
