// 应用层 — 媒体导入协调:选文件、构建 item、归一化、探测。

import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { mediaIpc } from '@/lib/ipc/endpoints/media'
import { createMediaItem } from '@/services/media/factory'
import {
  normalizeDecodeConfig,
  normalizeEncodeConfig,
} from '@/services/preset/normalize'
import { normalizeError } from '@/lib/errors/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol'

export function useMediaImport() {
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()
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

  async function reinspectIds(ids: string[]): Promise<void> {
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
    await reinspectIds(fresh.map((item) => item.id))
  }

  async function pickAndImport(): Promise<void> {
    try {
      const paths = await mediaIpc.pickInputs()
      await importPaths(paths)
    } catch (error) {
      issueStore.setIssue('input', normalizeError(error, TASK_ERROR_CODES.IoError))
    }
  }

  return {
    importPaths,
    pickAndImport,
    reinspectIds,
  }
}
