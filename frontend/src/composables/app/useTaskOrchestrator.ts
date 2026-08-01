// Application-level batch orchestration and UI-facing state projection.
// Runtime wiring remains isolated in ``taskOrchestratorRuntime.ts``.

import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import type { BatchRunner } from '@/services/task/batch-runner'
import { evaluateStartReadiness } from '@/services/task/preflight'
import { getTaskRunner } from './taskOrchestratorRuntime'

export function useTaskOrchestrator() {
  const mediaStore = useMediaStore()
  const taskStore = useTaskStore()

  // ``storeToRefs`` keeps the reactive bindings for ref / computed fields
  // when callers destructure the returned object — without it,
  // ``pendingConflict`` would lose its reactivity at the destructure
  // site.
  const { pendingConflict } = storeToRefs(taskStore)

  const batch = taskStore.batch

  // Keep the UI projection here while the reusable readiness rules live in
  // ``services/task/preflight.ts``.
  const preflightVerdict = computed(() =>
    evaluateStartReadiness({
      phase: taskStore.batch.phase,
      selectedItems: mediaStore.selectedItems.map((item) => ({
        displayName: item.displayName,
        inputPath: item.inputPath,
        outputDir: item.outputConfig.outputDir,
      })),
    }),
  )
  const canStartBatch = computed(() => preflightVerdict.value.ok)
  const cannotStartReason = computed(() => preflightVerdict.value.reason)
  async function startBatch(): Promise<void> {
    if (!canStartBatch.value) {
      return
    }
    await getTaskRunner().start(mediaStore.selectedIds)
  }

  async function pauseCurrentTask(): Promise<void> {
    await getTaskRunner().pause()
  }

  async function resumeCurrentTask(): Promise<void> {
    await getTaskRunner().resume()
  }

  async function interruptBatch(): Promise<void> {
    await getTaskRunner().cancel()
  }

  async function resolveConflict(action: Parameters<BatchRunner['resolveConflict']>[0]): Promise<void> {
    await getTaskRunner().resolveConflict(action)
  }

  return {
    batch,
    pendingConflict,
    canStartBatch,
    cannotStartReason,
    startBatch,
    pauseCurrentTask,
    resumeCurrentTask,
    interruptBatch,
    resolveConflict,
  }
}
