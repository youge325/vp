// 应用层 — 输出目录选择协调。
//
// Phase 16 — IO 错误路由到 ``useIssueStore.setIssue('encode', …)``,
// ``EncodeModuleView`` 的 ``IssueBanner :issue="useOperationIssue('encode')"``
// 自动消费。
//
// Phase 17 — 成功路径改走 ``useWorkbenchEditor.patchOutput`` 双轨路由:
// 有 activeItem 写到 active + selected 的素材级 outputConfig,无 activeItem
// 写到 preset.draftPreset.outputConfig。原先直调 ``presetStore.patchOutput``
// 在激活素材态下是真 bug —— 写到预设草稿后,view 的 ``editorConfig.outputConfig``
// 优先读 activeItem.outputConfig.outputDir,用户点选完路径输入框还是
// 旧值/空,体感"没生效"。
//
// 用户主动取消 dialog(``pickOutputDirectory`` 返回 null,而不是抛错)
// 走"无变化 + 清空旧 banner"路径,避免上次的 IO 错误条挂着。

import { useIssueStore } from '@/stores/issue'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
import { normalizeError } from '@/services/error/normalize'
import type { TaskError } from '@/types/domain/media'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'

export function useOutputPicker() {
  const issueStore = useIssueStore()
  const editor = useWorkbenchEditor()

  async function pickOutputDirectory(): Promise<{ outputDir: string | null; error: TaskError | null }> {
    try {
      const outputDir = await presetIpc.pickOutputDirectory()
      if (outputDir) {
        editor.patchOutput((config) => {
          config.outputDir = outputDir
        })
      }
      // 成功路径(含取消)同时清掉上次的 banner —— 用户重新点选择目录
      // 后旧错误条不该继续挂着。
      issueStore.clearIssue('encode')
      return { outputDir, error: null }
    } catch (error) {
      const normalised = normalizeError(error, TASK_ERROR_CODES.IoError)
      issueStore.setIssue('encode', normalised)
      return { outputDir: null, error: normalised }
    }
  }

  return { pickOutputDirectory }
}
