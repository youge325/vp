// 媒体运行时投影 store —— Phase 13.1 从 ``useMediaStore`` 拆出。
//
// ``useMediaStore`` 原本兼任 list CRUD + 每个 item 的运行时状态
// (``taskState`` / ``issue`` / ``lastOutputPath``),写入路径(batch
// lifecycle / events)和读取路径(TaskConsole / step-rail / app-shell)
// 都得绕进同一份 ``MediaItem`` 结构,导致 store 的关注点膨胀到 5 个。
//
// Phase 13.1 把"实体 list"和"运行时投影"分成两个 store:
//   - [[useMediaStore]] 只管 list CRUD(增删改激活/选中/info)
//   - 本 store 单独管 task 状态 / 最近输出路径
//
// 形状仍然是 ``Record<itemId, MediaRunState>``,通过 ``reactive`` 暴露
// 子键的响应式追踪能力;调用方在 ``computed`` 中读 ``getByItemId(id)?.X``
// 会被 Vue 正常跟踪,新增 key 也是响应式的(Vue 3 Proxy)。
//
// 未被 set 过的 itemId 直接返回 ``null`` —— 视图侧本来就在用
// ``?? null`` / ``?? []`` fallback,迁移痛感低。
//
// Phase 16 — ``issue`` 字段与 ``setIssue`` mutator 移除。任务错误现在
// 走 [[useIssueStore]] 的 ``'task'`` scope([[finalize.ts]] 的
// ``handleErrored`` + [[batch/events.ts]] ``onCancelled`` 的 stalled
// 分支),视图侧通过 ``useOperationIssue('task')`` 消费,本 store 不再
// 承载任何 banner state。

import { reactive } from 'vue'
import { defineStore } from 'pinia'
import { createIdleTaskState } from '@/services/task/events'
import type { MediaRunState, MediaTaskState } from '@/types/domain/media'

export const useMediaRunState = defineStore('mediaRunState', () => {
  const state = reactive<Record<string, MediaRunState>>({})

  function getByItemId(id: string | null | undefined): MediaRunState | null {
    if (!id) {
      return null
    }
    return state[id] ?? null
  }

  function ensure(id: string): MediaRunState {
    const existing = state[id]
    if (existing) {
      return existing
    }
    const fresh: MediaRunState = {
      taskState: createIdleTaskState(),
      lastOutputPath: '',
    }
    state[id] = fresh
    return fresh
  }

  function setTaskState(id: string, taskState: MediaTaskState): void {
    ensure(id).taskState = taskState
  }

  function setLastOutputPath(id: string, path: string): void {
    ensure(id).lastOutputPath = path
  }

  function setIdleRunState(id: string, logs: string[]): void {
    state[id] = {
      taskState: { ...createIdleTaskState(), logs },
      lastOutputPath: '',
    }
  }

  function resetItemRunState(id: string): void {
    setIdleRunState(id, [])
  }

  function resetItemsRunState(ids: Set<string>): void {
    for (const id of ids) {
      setIdleRunState(id, state[id]?.taskState.logs ?? [])
    }
  }

  function dropItem(id: string): void {
    delete state[id]
  }

  return {
    getByItemId,
    setTaskState,
    setLastOutputPath,
    resetItemRunState,
    resetItemsRunState,
    dropItem,
  }
})
