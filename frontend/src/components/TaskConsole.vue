<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { useMediaRunState } from '@/stores/mediaRunState'
import { classifyTaskLogLine, displayTaskLogLine } from '@/services/task/events'

const { consoleTaskItem, batch, batchTotal } = useTaskOrchestrator()
const runStateStore = useMediaRunState()
const terminalRef = ref<HTMLDivElement | null>(null)
// Phase 13.1 — taskState 已从 MediaItem 拆到独立 store,这里改成按
// itemId 二级 lookup。
const consoleRunState = computed(() => runStateStore.getByItemId(consoleTaskItem.value?.id))
const logs = computed(() => consoleRunState.value?.taskState.logs ?? [])
const resumeStatus = computed(() => consoleRunState.value?.taskState.resumeStatus ?? null)
const showResumeBanner = computed(() => Boolean(resumeStatus.value?.resumed))

const done = computed(() => batch.completedCount)
const total = computed(() => batchTotal.value)
const progressPercent = computed(() => {
  if (total.value === 0) {
    return 0
  }
  return Math.min(100, Math.round((done.value / total.value) * 100))
})

function logLineClass(line: string): string[] {
  return classifyTaskLogLine(line) === 'tensorrt' ? ['log-line-trt'] : []
}

// Phase D.4.8 — watch length instead of the array contents. The previous
// `deep: true` watcher fired on every progress-line replacement
// (`[VP_PROGRESS]` updates the matching stage line roughly once per
// backend percent tick) and forced a full panel reconcile every time.
// Listening to `length` means we only scroll on append, which is the
// visible behaviour the user actually cares about; progress-line tail
// updates keep the user's scroll position intact.
watch(
  () => logs.value.length,
  async () => {
    await nextTick()
    const panel = terminalRef.value
    if (!panel) {
      return
    }
    panel.scrollTop = panel.scrollHeight
  },
)
</script>

<template>
  <section class="task-console surface-subpanel">
    <div v-if="showResumeBanner && resumeStatus" class="resume-banner">
      <span class="resume-banner-icon">✓</span>
      <span>
        续传：已完成 {{ resumeStatus.completedChunks }} 段
        / 第 {{ resumeStatus.completedOutputFrames }} 帧
        <template v-if="resumeStatus.totalOutputFrames > 0">
          (共 {{ resumeStatus.totalOutputFrames }} 帧)
        </template>
      </span>
    </div>
    <div ref="terminalRef" class="log-panel log-panel-terminal">
      <p v-for="(line, index) in logs" :key="index" class="log-line" :class="logLineClass(line)">
        <span>{{ displayTaskLogLine(line) }}</span>
      </p>
    </div>
    <div class="progress-row">
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: `${progressPercent}%` }" />
      </div>
      <span class="progress-label">{{ done }} / {{ total }}</span>
    </div>
  </section>
</template>

<style scoped>
.resume-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  border-left: 3px solid #3aa569;
  background: rgba(58, 165, 105, 0.1);
  border-radius: 4px;
  font-size: 0.875rem;
  color: #d8f0e0;
}
.resume-banner-icon {
  color: #3aa569;
  font-weight: bold;
}
</style>
