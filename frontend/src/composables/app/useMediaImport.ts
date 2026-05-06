// 应用层 — 媒体导入协调:选文件、构建 item、归一化、探测。

import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { mediaIpc } from '@/lib/ipc/endpoints/media'
import { createMediaItem } from '@/services/media/factory'
import {
  normalizeDecodeConfig,
  normalizeEncodeConfig,
} from '@/services/preset/normalize'
import { normalizeTaskError } from '@/services/task/error-normalizer'

export function useMediaImport() {
  const envStore = useEnvStore()
  const mediaStore = useMediaStore()
  const presetStore = usePresetStore()

  async function inspectAndNormalize(itemId: string): Promise<void> {
    const item = mediaStore.findItem(itemId)
    if (!item || item.inspecting) {
      return
    }
    mediaStore.setInspecting(itemId, true)
    mediaStore.setItemIssue(itemId, null)
    try {
      const info = await mediaIpc.inspect(item.inputPath)
      mediaStore.setItemInfo(itemId, info)
      const decodeConfig = normalizeDecodeConfig(item.decodeConfig, envStore.env.checkResult, info.videoCodec)
      const encodeConfig = normalizeEncodeConfig(item.encodeConfig, envStore.env.checkResult)
      mediaStore.replaceItemConfig(itemId, { decodeConfig, encodeConfig })
    } catch (error) {
      mediaStore.setItemIssue(itemId, normalizeTaskError(error, 'inspect_failed'))
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

  async function pickAndImport(): Promise<{ paths: string[]; error: ReturnType<typeof normalizeTaskError> | null }> {
    try {
      const paths = await mediaIpc.pickInputs()
      await importPaths(paths)
      return { paths, error: null }
    } catch (error) {
      return { paths: [], error: normalizeTaskError(error, 'pick_inputs_failed') }
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
        workflowConfig: JSON.parse(JSON.stringify(presetStore.draftPreset.workflowConfig)),
        outputConfig: JSON.parse(JSON.stringify(presetStore.draftPreset.outputConfig)),
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
