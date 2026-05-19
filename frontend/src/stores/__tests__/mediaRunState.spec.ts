import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useMediaRunState } from '@/stores/mediaRunState'
import { createIdleTaskState } from '@/services/task/events'
import type { MediaTaskState, TaskError } from '@/types/domain/media'

// Phase 13.1 — useMediaRunState 是 useMediaStore 拆分出来后的运行时投影
// store,只管 taskState / issue / lastOutputPath,这些字段不再挂在
// MediaItem 上,而是按 itemId 二级 lookup。

const sampleTaskState = (overrides: Partial<MediaTaskState> = {}): MediaTaskState => ({
  ...createIdleTaskState(),
  ...overrides,
})

const sampleIssue: TaskError = {
  code: 'process_failed',
  message: 'boom',
  details: null,
}

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
    store.setTaskState('a', sampleTaskState({ status: 'running', percent: 42 }))

    const entry = store.getByItemId('a')
    expect(entry).not.toBeNull()
    expect(entry?.taskState.status).toBe('running')
    expect(entry?.taskState.percent).toBe(42)
    expect(entry?.issue).toBeNull()
    expect(entry?.lastOutputPath).toBe('')
  })

  it('setIssue lazily creates an entry and stores the issue', () => {
    const store = useMediaRunState()
    store.setIssue('a', sampleIssue)

    const entry = store.getByItemId('a')
    expect(entry?.issue).toEqual(sampleIssue)
    expect(entry?.taskState.status).toBe('idle')
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
    store.setTaskState('a', sampleTaskState({ status: 'running', percent: 10 }))
    store.setTaskState('b', sampleTaskState({ status: 'completed', percent: 100 }))

    expect(store.getByItemId('a')?.taskState.status).toBe('running')
    expect(store.getByItemId('b')?.taskState.status).toBe('completed')
    expect(store.getByItemId('a')?.taskState.percent).toBe(10)
    expect(store.getByItemId('b')?.taskState.percent).toBe(100)
  })

  it('resetItemRunState restores idle defaults and clears logs by default', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({
      status: 'completed',
      percent: 100,
      logs: ['line-1', 'line-2'],
    }))
    store.setIssue('a', sampleIssue)
    store.setLastOutputPath('a', 'D:/out/a.mp4')

    store.resetItemRunState('a')

    const entry = store.getByItemId('a')
    expect(entry?.taskState.status).toBe('idle')
    expect(entry?.taskState.percent).toBe(0)
    expect(entry?.taskState.logs).toEqual([])
    expect(entry?.issue).toBeNull()
    expect(entry?.lastOutputPath).toBe('')
  })

  it('resetItemRunState preserves logs when asked', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({
      status: 'completed',
      percent: 100,
      logs: ['line-1', 'line-2'],
    }))

    store.resetItemRunState('a', true)

    const entry = store.getByItemId('a')
    expect(entry?.taskState.status).toBe('idle')
    expect(entry?.taskState.logs).toEqual(['line-1', 'line-2'])
  })

  it('resetItemRunState materialises a fresh entry for ids that were never set', () => {
    // 启动批处理时会一次性 reset 所有 runtime ids,即使其中某些 id 还没被
    // task state 触碰过 —— 必须能 idempotently 把它们移到 idle defaults。
    const store = useMediaRunState()
    store.resetItemRunState('first-time')

    const entry = store.getByItemId('first-time')
    expect(entry?.taskState.status).toBe('idle')
    expect(entry?.issue).toBeNull()
    expect(entry?.lastOutputPath).toBe('')
  })

  it('resetItemsRunState resets every id in the set', () => {
    const store = useMediaRunState()
    store.setTaskState('a', sampleTaskState({ status: 'completed' }))
    store.setTaskState('b', sampleTaskState({ status: 'error' }))
    store.setTaskState('c', sampleTaskState({ status: 'completed' }))

    store.resetItemsRunState(new Set(['a', 'b']))

    expect(store.getByItemId('a')?.taskState.status).toBe('idle')
    expect(store.getByItemId('b')?.taskState.status).toBe('idle')
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
})
