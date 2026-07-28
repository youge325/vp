import { describe, expect, it } from 'vitest'

import {
  TASK_EVENT_NAMES,
  TERMINAL_PROGRESS_PREFIX,
  type TaskEventName,
} from '@/types/protocol/events'

const EXPECTED_VARIANTS: readonly TaskEventName[] = [
  'task-progress',
  'task-completed',
  'task-error',
  'task-cancelled',
  'task-log',
  'task-resume-status',
] as const

describe('TASK_EVENT_NAMES', () => {
  it('values cover every TaskEventName variant', () => {
    const actualValues = new Set(Object.values(TASK_EVENT_NAMES))
    const expectedValues = new Set(EXPECTED_VARIANTS)
    expect(actualValues).toEqual(expectedValues)
  })

  it('values are unique', () => {
    const values = Object.values(TASK_EVENT_NAMES)
    expect(new Set(values).size).toBe(values.length)
  })

  it('all values follow the task-<kebab> convention', () => {
    for (const value of Object.values(TASK_EVENT_NAMES)) {
      expect(value).toMatch(/^task(-[a-z]+)+$/)
    }
  })

  it('exports the backend stderr progress prefix', () => {
    expect(TERMINAL_PROGRESS_PREFIX).toBe('[VP_PROGRESS]')
  })
})
