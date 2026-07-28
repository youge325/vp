<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useTaskConsoleState } from '@/composables/selectors/useTaskConsoleState'

const {
  logs,
  resumeStatus,
  showResumeBanner,
  done,
  total,
  progressPercent,
} = useTaskConsoleState()
const terminalRef = ref<HTMLDivElement | null>(null)

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
      <p v-for="(line, index) in logs" :key="index" class="log-line">
        <span>{{ line }}</span>
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
