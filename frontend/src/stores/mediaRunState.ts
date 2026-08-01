// 媒体运行时投影 store,单独管理每个素材的任务状态与最近输出路径。
// 形状仍然是 ``Record<itemId, MediaRunState>``,通过 ``reactive`` 暴露
// 子键的响应式追踪能力;调用方在 ``computed`` 中读 ``getByItemId(id)?.X``
// 会被 Vue 正常跟踪,新增 key 也是响应式的(Vue 3 Proxy)。
// 未被 set 过的 itemId 直接返回 ``null`` —— 视图侧本来就在用
// ``?? null`` / ``?? []`` fallback。用户可见错误由 ``useIssueStore`` 管理。

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

  function resetItemRunState(id: string): void {
    state[id] = {
      taskState: createIdleTaskState(),
      lastOutputPath: '',
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
    dropItem,
  }
})
