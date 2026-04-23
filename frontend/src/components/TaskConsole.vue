<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()
const terminalRef = ref<HTMLDivElement | null>(null)
const logs = computed(() => store.consoleTaskItem?.taskState.logs ?? [])

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
  </section>
</template>
