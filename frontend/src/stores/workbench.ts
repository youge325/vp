import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  applyTaskCancelled,
  applyTaskCompleted,
  applyTaskError,
  applyTaskProgress,
  appendTaskLog,
  createIdleTaskState,
} from '@/lib/task-events'
import { buildSummarySections, buildTaskRequest } from '@/lib/task-mapper'
import {
  cancelTask as cancelRuntimeTask,
  checkEnvironment as checkRuntimeEnvironment,
  inspectVideo as inspectRuntimeVideo,
  listenTaskEvents,
  openFileOrDirectory as openRuntimePath,
  openOutputLocation as openRuntimeOutputLocation,
  pickInput as pickRuntimeInput,
  pickOutput as pickRuntimeOutput,
  startTask as startRuntimeTask,
} from '@/lib/tauri'
import type {
  AppEnv,
  AnimeOptimizationSettings,
  EncodeSettings,
  EnvironmentCheckResult,
  FormatConversionSettings,
  InterpolationSettings,
  OutputSettings,
  SourceMedia,
  SuperResolutionSettings,
  TaskError,
  WorkflowSelection,
  WorkbenchStateSnapshot,
} from '@/types'

function defaultEnv(): AppEnv {
  return {
    lastCheckedAt: null,
    isChecking: false,
    checkResult: null,
    issue: null,
  }
}

function defaultSource(): SourceMedia {
  return {
    inputPath: '',
    inspecting: false,
    info: null,
  }
}

function defaultWorkflow(): WorkflowSelection {
  return {
    primaryMode: 'frame_interpolation',
    enableInterpolation: true,
    enableSuperResolution: false,
    processOrder: 'super_resolution_then_interpolation',
    fpsMode: 'target',
  }
}

function defaultInterpolation(): InterpolationSettings {
  return {
    targetFps: 60,
    multi: 2,
    model: '4.25',
    scale: 1,
    fp16: false,
    tensorBackend: 'pytorch',
  }
}

function defaultSuperResolution(): SuperResolutionSettings {
  return {
    enabled: false,
    scaleFactor: 2,
    algorithm: 'placeholder',
  }
}

function defaultAnime(): AnimeOptimizationSettings {
  return {
    enabled: false,
    profile: 'clean-lines',
    denoise: 10,
    edgeBoost: 15,
  }
}

function defaultFormat(): FormatConversionSettings {
  return {
    remuxOnly: false,
    keepAudio: true,
    container: 'mp4',
  }
}

function defaultEncode(): EncodeSettings {
  return {
    codec: 'libx264',
    crf: 18,
    preset: 'medium',
  }
}

function defaultOutput(): OutputSettings {
  return {
    outputPath: '',
    outputDir: '',
    tempDir: '',
    openOnComplete: true,
  }
}

export const useWorkbenchStore = defineStore('workbench', () => {
  const env = ref(defaultEnv())
  const source = ref(defaultSource())
  const workflow = ref(defaultWorkflow())
  const interpolation = ref(defaultInterpolation())
  const superResolution = ref(defaultSuperResolution())
  const anime = ref(defaultAnime())
  const format = ref(defaultFormat())
  const encode = ref(defaultEncode())
  const output = ref(defaultOutput())
  const task = ref(createIdleTaskState())

  const listenersAttached = ref(false)
  let teardown: (() => void) | null = null

  const snapshot = computed<WorkbenchStateSnapshot>(() => ({
    env: env.value,
    source: source.value,
    workflow: workflow.value,
    interpolation: interpolation.value,
    superResolution: superResolution.value,
    anime: anime.value,
    format: format.value,
    encode: encode.value,
    output: output.value,
    task: task.value,
  }))

  const summarySections = computed(() => buildSummarySections(snapshot.value))

  const canStartTask = computed(() => {
    if (task.value.status === 'running') {
      return false
    }

    if (!source.value.inputPath.trim()) {
      return false
    }

    if (
      (workflow.value.primaryMode === 'frame_interpolation' ||
        workflow.value.primaryMode === 'super_resolution') &&
      !workflow.value.enableInterpolation &&
      !workflow.value.enableSuperResolution
    ) {
      return false
    }

    return true
  })

  function setPrimaryMode(mode: WorkflowSelection['primaryMode']) {
    workflow.value.primaryMode = mode

    if (mode === 'frame_interpolation') {
      workflow.value.enableInterpolation = true
      workflow.value.enableSuperResolution = superResolution.value.enabled
    } else if (mode === 'super_resolution') {
      workflow.value.enableInterpolation = false
      workflow.value.enableSuperResolution = true
      superResolution.value.enabled = true
    } else {
      workflow.value.enableInterpolation = false
      workflow.value.enableSuperResolution = false
    }
  }

  function setIssue(error: TaskError) {
    env.value.issue = error
    task.value = applyTaskError(task.value, error)
  }

  async function attachTaskListeners() {
    if (listenersAttached.value) {
      return
    }

    teardown = await listenTaskEvents({
      onProgress(payload) {
        task.value = applyTaskProgress(task.value, payload)
      },
      onLog(payload) {
        task.value = appendTaskLog(task.value, payload)
      },
      onCompleted(payload) {
        task.value = applyTaskCompleted(task.value, payload)
        if (payload.outputPath) {
          output.value.outputPath = output.value.outputPath || payload.outputPath
        }
      },
      onError(error) {
        task.value = applyTaskError(task.value, error)
      },
      onCancelled() {
        task.value = applyTaskCancelled(task.value)
      },
    })
    listenersAttached.value = true
  }

  function detachTaskListeners() {
    teardown?.()
    teardown = null
    listenersAttached.value = false
  }

  async function pickInput() {
    const selected = await pickRuntimeInput()
    if (!selected) {
      return
    }

    source.value.inputPath = selected
    source.value.info = null
  }

  async function pickOutput() {
    const filename = source.value.inputPath
      ? `${source.value.inputPath.split(/[/\\\\]/).pop()?.replace(/\.[^.]+$/, '') ?? 'output'}_processed.mp4`
      : 'output_processed.mp4'
    const selected = await pickRuntimeOutput(filename)
    if (selected) {
      output.value.outputPath = selected
    }
  }

  async function checkEnvironment() {
    env.value.isChecking = true
    env.value.issue = null

    try {
      const result = await checkRuntimeEnvironment()
      env.value.checkResult = result as EnvironmentCheckResult
      env.value.lastCheckedAt = new Date().toISOString()
    } catch (error) {
      setIssue({
        code: 'missing_runtime',
        message: error instanceof Error ? error.message : '环境检查失败。',
        details: null,
      })
    } finally {
      env.value.isChecking = false
    }
  }

  async function inspectVideo() {
    if (!source.value.inputPath.trim()) {
      setIssue({
        code: 'invalid_input',
        message: '请先选择输入视频。',
        details: null,
      })
      return
    }

    source.value.inspecting = true
    try {
      source.value.info = await inspectRuntimeVideo(source.value.inputPath.trim())
    } catch (error) {
      setIssue({
        code: 'invalid_input',
        message: error instanceof Error ? error.message : '素材信息读取失败。',
        details: null,
      })
    } finally {
      source.value.inspecting = false
    }
  }

  async function startTask() {
    task.value = {
      ...createIdleTaskState(),
      status: 'running',
      startedAt: new Date().toISOString(),
    }
    env.value.issue = null
    await attachTaskListeners()

    try {
      await startRuntimeTask(buildTaskRequest(snapshot.value))
    } catch (error) {
      task.value = applyTaskError(task.value, {
        code: 'process_failed',
        message: error instanceof Error ? error.message : '任务启动失败。',
        details: null,
      })
    }
  }

  async function cancelCurrentTask() {
    try {
      await cancelRuntimeTask()
    } catch (error) {
      task.value = applyTaskError(task.value, {
        code: 'cancelled',
        message: error instanceof Error ? error.message : '取消任务失败。',
        details: null,
      })
    }
  }

  async function openOutputLocation() {
    const path = task.value.outputPath || output.value.outputPath
    if (!path) {
      return
    }

    await openRuntimeOutputLocation(path)
  }

  async function openFileOrDirectory(path: string) {
    if (!path) {
      return
    }

    await openRuntimePath(path)
  }

  return {
    env,
    source,
    workflow,
    interpolation,
    superResolution,
    anime,
    format,
    encode,
    output,
    task,
    summarySections,
    canStartTask,
    snapshot,
    setPrimaryMode,
    attachTaskListeners,
    detachTaskListeners,
    pickInput,
    pickOutput,
    checkEnvironment,
    inspectVideo,
    startTask,
    cancelCurrentTask,
    openOutputLocation,
    openFileOrDirectory,
  }
})
