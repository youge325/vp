// 应用层 — 输出目录选择协调。
//
// Phase 16 — IO 错误现在路由到 ``useIssueStore.setIssue('encode', …)``,
// ``EncodeModuleView`` 的 ``IssueBanner :issue="useOperationIssue('encode')"``
// 自动消费。Phase 14 与 ``useMediaImport`` 修通 ``'input'`` scope 同款思路 ——
// 把已有的 5-scope IssueStore 抽象用对地方,不引入新结构。
//
// 用户主动取消 dialog(``pickOutputDirectory`` 返回空字符串 / null,而不
// 是抛错)走"无变化 + 清空旧 banner"路径,避免上次的 IO 错误条挂着。

import { useIssueStore } from '@/stores/issue'
import { usePresetStore } from '@/stores/preset'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
import { normalizeError } from '@/services/error/normalize'
import type { TaskError } from '@/types/domain/media'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'
import type { OutputConfig } from '@/types/protocol'

export function useOutputPicker() {
  const issueStore = useIssueStore()
  const presetStore = usePresetStore()

  async function pickOutputDirectory(): Promise<{ outputDir: string | null; error: TaskError | null }> {
    try {
      const outputDir = await presetIpc.pickOutputDirectory()
      if (outputDir) {
        presetStore.patchOutput((config: OutputConfig) => {
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
