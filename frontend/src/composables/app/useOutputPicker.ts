// 应用层 — 输出目录选择协调。成功时按当前编辑范围写回配置，
// 失败时把错误路由到 encode issue，取消选择只清理旧错误。

import { useIssueStore } from '@/stores/issue'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'

export function useOutputPicker() {
  const issueStore = useIssueStore()
  const editor = useWorkbenchEditor()

  async function pickOutputDirectory(): Promise<void> {
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
    } catch (error) {
      issueStore.setIssue('encode', normalizeError(error, TASK_ERROR_CODES.IoError))
    }
  }

  return { pickOutputDirectory }
}
