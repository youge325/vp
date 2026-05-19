// 应用层 — 媒体导入协调:选文件、构建 item、归一化、探测。

import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { mediaIpc } from '@/lib/ipc/endpoints/media'
import { createMediaItem } from '@/services/media/factory'
import {
  cloneOutputConfig,
  cloneWorkflowConfig,
} from '@/services/preset/clone'
import {
  normalizeDecodeConfig,
  normalizeEncodeConfig,
} from '@/services/preset/normalize'
import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'
import type { TaskError } from '@/types/domain/media'

export function useMediaImport() {
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()
  // Phase 14 — 把"导入失败"路由到 issueStore('input') scope,InputModuleView
  // 的 ``useOperationIssue('input')`` 才能拿到、IssueBanner 才会显示。
  //
  // Phase 13.1 改 ``useMediaImport`` 写入 ``mediaRunState.setIssue(itemId, …)``
  // 时,实际上没有任何视图侧消费方读 ``mediaRunState.getByItemId(id)?.issue``,
  // 导入失败时 banner 永远不出现 —— 是真 dead write。改到 issueStore 后
  // 同一个 import 工作流的失败会覆盖前一次的 banner 文案(per-scope 单
  // banner 是设计),展示最后一次错误足够提示用户。
  const issueStore = useIssueStore()
  const presetStore = usePresetStore()

  async function inspectAndNormalize(itemId: string): Promise<void> {
    const item = mediaStore.findItem(itemId)
    if (!item || item.inspecting) {
      return
    }
    mediaStore.setInspecting(itemId, true)
    issueStore.clearIssue('input')
    try {
      const info = await mediaIpc.inspect(item.inputPath)
      mediaStore.setItemInfo(itemId, info)
      const decodeConfig = normalizeDecodeConfig(item.decodeConfig, envStore.env.checkResult, info.videoCodec)
      const encodeConfig = normalizeEncodeConfig(item.encodeConfig, envStore.env.checkResult)
      mediaStore.replaceItemConfig(itemId, { decodeConfig, encodeConfig })
    } catch (error) {
      issueStore.setIssue('input', normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    } finally {
      mediaStore.setInspecting(itemId, false)
    }
  }

  async function inspectItems(ids: string[]): Promise<void> {
    await Promise.allSettled(ids.map((id) => inspectAndNormalize(id)))
  }

  async function importPaths(paths: string[]): Promise<void> {
    const normalizedPaths = paths.filter(Boolean)
    const existing = new Set(mediaStore.mediaItems.map((item) => item.inputPath.toLowerCase()))
    const fresh = normalizedPaths
      .filter((path) => !existing.has(path.toLowerCase()))
      .map((path) => createMediaItem(path, presetStore.draftPreset))

    if (fresh.length === 0) {
      return
    }

    mediaStore.appendItems(fresh)
    mediaStore.setActive(fresh[0]?.id ?? null)
    await inspectItems(fresh.map((item) => item.id))
  }

  async function pickAndImport(): Promise<{ paths: string[]; error: TaskError | null }> {
    try {
      const paths = await mediaIpc.pickInputs()
      await importPaths(paths)
      return { paths, error: null }
    } catch (error) {
      return { paths: [], error: normalizeError(error, TASK_ERROR_CODES.IoError) }
    }
  }

  function reinspectIds(ids: string[]): Promise<void> {
    return inspectItems(ids)
  }

  function applyDraftToSelectedItems(): void {
    const targetIds = mediaStore.getEditableTargetIds()
    for (const item of mediaStore.mediaItems) {
      if (!targetIds.has(item.id)) {
        continue
      }
      const decodeConfig = normalizeDecodeConfig(presetStore.draftPreset.decodeConfig, envStore.env.checkResult, item.info?.videoCodec ?? '', true)
      const encodeConfig = normalizeEncodeConfig(presetStore.draftPreset.encodeConfig, envStore.env.checkResult, true)
      mediaStore.replaceItemConfig(item.id, {
        decodeConfig,
        encodeConfig,
        workflowConfig: cloneWorkflowConfig(presetStore.draftPreset.workflowConfig),
        outputConfig: cloneOutputConfig(presetStore.draftPreset.outputConfig),
      })
    }
  }

  return {
    importPaths,
    pickAndImport,
    reinspectIds,
    applyDraftToSelectedItems,
  }
}
