import type { WorkbenchPreset } from '@/types/protocol'
import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'

export function createTestPreset(
  output: Partial<WorkbenchPreset['outputConfig']> = {},
): WorkbenchPreset {
  const workflowConfig = createDefaultWorkflowConfigForEnvironment(null)
  workflowConfig.interpolation.enabled = false

  return {
    decodeConfig: {
      mode: 'software',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'software',
      options: {},
    },
    workflowConfig,
    encodeConfig: {
      codec: 'libx265',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf', value: 18 },
      options: {},
    },
    outputConfig: {
      outputDir: '',
      openOnComplete: true,
      segmentFrames: 1000,
      ...output,
    },
  }
}
