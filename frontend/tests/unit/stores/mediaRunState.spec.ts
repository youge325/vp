import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useMediaRunState } from '@/stores/mediaRunState'
import { createIdleTaskState } from '@/services/task/events'
import type { MediaTaskState } from '@/types/domain/media'

// Phase 13.1 — useMediaRunState 是 useMediaStore 拆分出来后的运行时投影
// store,只管 taskState / lastOutputPath,这些字段不再挂在 MediaItem
// 上,而是按 itemId 二级 lookup。
//
// Phase 16 — ``issue`` 字段与 ``setIssue`` 移除。错误现在统一走
// [[useIssueStore]] 的 ``'task'`` scope([[finalize.ts]] / [[batch/events.ts]]),
// 本 store 只剩运行时进度投影。spec 同步去掉所有 issue 相关断言。

const sampleTaskState = (overrides: Partial<MediaTaskState> = {}): MediaTaskState => ({
  ...createIdleTaskState(),
  ...overrides,
})

describe('useMediaRunState', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('returns null for items that have never been touched', () => {
    const store = useMediaRunState()
    expect(store.getByItemId('never-set')).toBeNull()
  })

  it('returns null when asked for a nullish id', () => {
    const store = useMediaRunState()
    expect(store.getByItemId(null)).toBeNull()
    expect(store.getByItemId(undefined)).toBeNull()
    expect(store.getByItemId('')).toBeNull()
  })

  it('setTaskState lazily creates an entry with sensible defaults', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({ status: 'running' }))

    const entry = store.getByItemId('a')
    expect(entry).not.toBeNull()
    expect(entry?.taskState.status).toBe('running')
    expect(entry?.lastOutputPath).toBe('')
  })

  it('setLastOutputPath lazily creates an entry and stores the path', () => {
    const store = useMediaRunState()
    store.setLastOutputPath('a', 'D:/out/a.mp4')

    const entry = store.getByItemId('a')
    expect(entry?.lastOutputPath).toBe('D:/out/a.mp4')
    expect(entry?.taskState.status).toBe('idle')
  })

  it('keeps unrelated entries isolated when set on different ids', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({ status: 'running' }))
    store.setTaskState('b', sampleTaskState({ status: 'completed' }))

    expect(store.getByItemId('a')?.taskState.status).toBe('running')
    expect(store.getByItemId('b')?.taskState.status).toBe('completed')
  })

  it('resetItemRunState restores idle defaults and clears logs', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({
      status: 'completed',
      logs: ['line-1', 'line-2'],
    }))
    store.setLastOutputPath('a', 'D:/out/a.mp4')

    store.resetItemRunState('a')

    const entry = store.getByItemId('a')
    expect(entry?.taskState.status).toBe('idle')
    expect(entry?.taskState.logs).toEqual([])
    expect(entry?.lastOutputPath).toBe('')
  })

  it('resetItemRunState materialises a fresh entry for ids that were never set', () => {
    // 启动批处理时会一次性 reset 所有 runtime ids,即使其中某些 id 还没被
    // task state 触碰过 —— 必须能 idempotently 把它们移到 idle defaults。
    const store = useMediaRunState()
    store.resetItemRunState('first-time')

    const entry = store.getByItemId('first-time')
    expect(entry?.taskState.status).toBe('idle')
    expect(entry?.lastOutputPath).toBe('')
  })

  it('resetItemsRunState resets every id while preserving batch logs', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({ status: 'completed', logs: ['a-log'] }))
    store.setTaskState('b', sampleTaskState({ status: 'error', logs: ['b-log'] }))
    store.setTaskState('c', sampleTaskState({ status: 'completed' }))

    store.resetItemsRunState(new Set(['a', 'b']))

    expect(store.getByItemId('a')?.taskState.status).toBe('idle')
    expect(store.getByItemId('b')?.taskState.status).toBe('idle')
    expect(store.getByItemId('a')?.taskState.logs).toEqual(['a-log'])
    expect(store.getByItemId('b')?.taskState.logs).toEqual(['b-log'])
    // 不在 set 里的 id 状态保持不变
    expect(store.getByItemId('c')?.taskState.status).toBe('completed')
  })

  it('dropItem removes the entry entirely', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({ status: 'running' }))
    expect(store.getByItemId('a')).not.toBeNull()

    store.dropItem('a')
    expect(store.getByItemId('a')).toBeNull()
  })

  // Phase 16 — 锁住 setIssue 已下线,如果将来有人想再把 banner state
  // 塞回这个 store(违反"banner 走 issueStore"约定),回归测试会立刻 fail。
  it('does not expose setIssue after Phase 16', () => {
    const store = useMediaRunState()
    expect('setIssue' in store).toBe(false)
  })
})
