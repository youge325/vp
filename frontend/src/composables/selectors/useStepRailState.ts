import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { useOperationIssue } from '@/composables/selectors/useOperationIssue'
import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import { DEFAULT_WORKBENCH_MODULE_KEY, type ModuleKey } from '@/config/workbench-modules'

export function useStepRailState() {
  const route = useRoute()
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()
  const taskStore = useTaskStore()
  const { editorConfig } = useWorkbenchEditor()
  const environmentIssue = useOperationIssue('environment')

  const activeModuleKey = computed<ModuleKey>(
    () => route.meta.module?.key ?? DEFAULT_WORKBENCH_MODULE_KEY,
  )

  const moduleStates = computed<Record<ModuleKey, string>>(() => {
    const env = envStore.env.checkResult
    const wf = editorConfig.value.workflowConfig
    return {
      home: env || environmentIssue.value ? 'ready' : 'idle',
      input: mediaStore.mediaItems.length > 0 ? 'ready' : 'idle',
      decode: env ? 'ready' : 'idle',
      preprocess: wf.preprocess.enabled ? 'ready' : 'idle',
      enhance: env ? 'ready' : 'idle',
      postprocess: wf.postprocess.enabled ? 'ready' : 'idle',
      encode: env && getVisibleEncoderProfiles(env).length > 0 ? 'ready' : 'idle',
      render: taskStore.batch.phase !== 'idle' ||
        (mediaStore.selectedItems.length > 0 && mediaStore.selectedItems.every((item) => Boolean(item.inputPath)))
        ? 'ready' : 'idle',
    }
  })

  return { activeModuleKey, moduleStates }
}
