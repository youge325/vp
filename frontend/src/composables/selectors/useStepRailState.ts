import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { useCurrentTaskStatusLabel } from '@/composables/selectors/useCurrentTaskStatusLabel'
import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import { getWorkflowSummaryLabel } from '@/services/format/labels'
import { DEFAULT_WORKBENCH_MODULE_KEY, type ModuleKey } from '@/config/workbench-modules'

export function useStepRailState() {
  const route = useRoute()
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()
  const taskStore = useTaskStore()
  const { editorConfig, isPresetMode } = useWorkbenchEditor()
  const taskStatusLabel = useCurrentTaskStatusLabel()

  const activeModuleKey = computed<ModuleKey>(
    () => route.meta.module?.key ?? DEFAULT_WORKBENCH_MODULE_KEY,
  )

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
      render: taskStore.batch.isRunning ||
        (mediaStore.selectedItems.length > 0 && mediaStore.selectedItems.every((item) => Boolean(item.inputPath)))
        ? 'ready' : 'idle',
    }
  })

  const workflowLabel = computed(() =>
    getWorkflowSummaryLabel(editorConfig.value.workflowConfig),
  )

  const selectionLabel = computed(() =>
    isPresetMode.value
      ? '默认预设'
      : `${mediaStore.selectedIds.length || 1}/${mediaStore.mediaItems.length} 已选`,
  )

  return { activeModuleKey, moduleStates, workflowLabel, selectionLabel, taskStatusLabel }
}
