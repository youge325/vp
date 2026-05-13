<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import type { ResumeConflictAction, ResumeConflictDescriptor } from '@/types/domain/batch'

const props = defineProps<{
  descriptor: ResumeConflictDescriptor
}>()

const emit = defineEmits<{
  resolve: [action: ResumeConflictAction]
}>()

const inspection = computed(() => props.descriptor.inspection)
const hasResume = computed(
  () => props.descriptor.kind === 'final_exists_with_resume' && inspection.value.completedChunks > 0,
)

const headline = computed(() => {
  if (hasResume.value) {
    return '检测到先前进度'
  }
  return '输出文件已存在'
})

const message = computed(() => {
  if (hasResume.value) {
    const completed = inspection.value.completedOutputFrames
    const total = inspection.value.totalOutputFrames
    const totalLabel = total > 0 ? ` / ${total}` : ''
    return `已找到 ${inspection.value.completedChunks} 段缓存（第 ${completed}${totalLabel} 帧），是否继续？`
  }
  return `目标路径已存在最终成品文件：\n${props.descriptor.outputPath}`
})

function handle(action: ResumeConflictAction): void {
  emit('resolve', action)
}

// Phase D.5.4 — a11y polish:
// - Esc resolves to ``cancel`` so keyboard users can dismiss a stuck
//   dialog without mouse navigation.
// - Overlay click (outside the dialog box) also cancels — matches the
//   pattern the system file dialogs already use.
// - Default focus lands on the most-likely action: ``resume`` when
//   it's offered, otherwise the destructive ``fresh`` (since at that
//   point the user is forced to choose between overwrite / skip /
//   cancel).
// - ``aria-labelledby`` / ``aria-describedby`` wire the title +
//   message into the dialog for screen readers.
const primaryButtonRef = ref<HTMLButtonElement | null>(null)
const titleId = 'resume-conflict-title'
const messageId = 'resume-conflict-message'
const previouslyFocused = ref<HTMLElement | null>(null)

function handleEscape(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    handle('cancel')
  }
}

onMounted(async () => {
  previouslyFocused.value = (document.activeElement as HTMLElement | null) ?? null
  document.addEventListener('keydown', handleEscape)
  await nextTick()
  primaryButtonRef.value?.focus()
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
  // Restore focus to the element that triggered the dialog so the user
  // returns to their place in the form (e.g. the Render view start button).
  previouslyFocused.value?.focus()
})
</script>

<template>
  <div
    class="resume-conflict-overlay"
    role="dialog"
    aria-modal="true"
    :aria-labelledby="titleId"
    :aria-describedby="messageId"
    @click.self="handle('cancel')"
  >
    <div class="resume-conflict-dialog">
      <h3 :id="titleId" class="resume-conflict-title">{{ headline }}</h3>
      <p :id="messageId" class="resume-conflict-message">{{ message }}</p>
      <p class="resume-conflict-output" v-if="hasResume">{{ descriptor.outputPath }}</p>
      <div class="resume-conflict-actions">
        <button
          v-if="hasResume"
          ref="primaryButtonRef"
          class="primary-button"
          type="button"
          @click="handle('resume')"
        >
          继续续传
        </button>
        <button
          v-else
          ref="primaryButtonRef"
          class="ghost-button"
          type="button"
          @click="handle('fresh')"
        >
          覆盖
        </button>
        <button v-if="hasResume" class="ghost-button" type="button" @click="handle('fresh')">重新开始</button>
        <button class="ghost-button" type="button" @click="handle('skip')">跳过此任务</button>
        <button class="ghost-button" type="button" @click="handle('cancel')">取消批次</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resume-conflict-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.resume-conflict-dialog {
  background: #1c2030;
  color: #e6e9f2;
  border-radius: 8px;
  padding: 1.5rem;
  max-width: 32rem;
  width: 90%;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
}
.resume-conflict-title {
  margin: 0 0 0.75rem;
  font-size: 1.1rem;
}
.resume-conflict-message {
  margin: 0 0 0.5rem;
  white-space: pre-line;
  line-height: 1.5;
}
.resume-conflict-output {
  margin: 0 0 1rem;
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 0.85rem;
  color: #a4abc1;
  word-break: break-all;
}
.resume-conflict-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
