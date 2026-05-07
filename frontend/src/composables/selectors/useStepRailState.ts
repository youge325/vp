import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import { getTaskStatusLabel } from '@/services/format/labels'
import { WORKBENCH_MODULE_KEYS } from '@/config/workbench-modules'
import type { ModuleKey, WorkbenchModuleDefinition } from '@/types/view/modules'

export function useStepRailState() {
  const route = useRoute()
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()
  const { editorConfig, isPresetMode } = useWorkbenchEditor()
  const { batch, currentTaskItem } = useTaskOrchestrator()

  const activeModuleKey = computed<ModuleKey>(() => {
    const module = route.meta.module as WorkbenchModuleDefinition | undefined
    return module?.key ?? WORKBENCH_MODULE_KEYS[0]
  })

  const moduleStates = computed<Record<ModuleKey, string>>(() => {
    const env = envStore.env.checkResult
    const wf = editorConfig.value.workflowConfig
    return {
      home: env || envStore.env.issue ? 'ready' : 'idle',
      input: mediaStore.mediaItems.length > 0 ? 'ready' : 'idle',
      decode: env ? 'ready' : 'idle',
      preprocess: wf.preprocess.enabled ? 'ready' : 'idle',
      enhance: env ? 'ready' : 'idle',
      postprocess: wf.postprocess.enabled ? 'ready' : 'idle',
      encode: env && getVisibleEncoderProfiles(env).length > 0 ? 'ready' : 'idle',
      render: batch.isRunning ||
        (mediaStore.selectedItems.length > 0 && mediaStore.selectedItems.every((item) => Boolean(item.inputPath)))
        ? 'ready' : 'idle',
    }
  })

  const workflowLabel = computed(() => {
    const wf = editorConfig.value.workflowConfig
    const enabled = [
      wf.interpolation.enabled ? '补帧' : null,
      wf.superResolution.enabled ? '超分' : null,
      wf.anime.enabled ? '动漫' : null,
    ].filter(Boolean)
    return enabled.length > 0 ? enabled.join(' / ') : '转码'
  })

  const selectionLabel = computed(() =>
    isPresetMode.value
      ? '默认预设'
      : `${mediaStore.selectedIds.length || 1}/${mediaStore.mediaItems.length} 已选`,
  )

  const taskStatusLabel = computed(() =>
    getTaskStatusLabel(batch, currentTaskItem.value?.taskState.status ?? null),
  )

  return { activeModuleKey, moduleStates, workflowLabel, selectionLabel, taskStatusLabel }
}
