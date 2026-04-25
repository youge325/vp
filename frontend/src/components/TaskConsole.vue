<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()
const terminalRef = ref<HTMLDivElement | null>(null)
const logs = computed(() => taskStore.consoleTaskItem?.taskState.logs ?? [])

const done = computed(() => taskStore.batch.completedCount)
const total = computed(() => taskStore.batchTotal)
const progressPercent = computed(() => {
  if (total.value === 0) {
    return 0
  }
  return Math.min(100, Math.round((done.value / total.value) * 100))
})

watch(
  logs,
  async () => {
    await nextTick()
    const panel = terminalRef.value
    if (!panel) {
      return
    }
    panel.scrollTop = panel.scrollHeight
  },
  { deep: true },
)
</script>

<template>
  <section class="task-console surface-subpanel">
    <div ref="terminalRef" class="log-panel log-panel-terminal">
      <p v-for="(line, index) in logs" :key="`${index}-${line}`" class="log-line">
        {{ line }}
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
