import { describe, expect, it } from 'vitest'
import type {
  IpcCommand,
  IpcInvokeArgs,
  IpcInvokeResult,
} from '@/lib/ipc/contract'

const inspectArgs: IpcInvokeArgs<'inspect_video'> = { inputPath: 'C:/media/input.mp4' }
const environmentArgs: IpcInvokeArgs<'check_environment'> = { forceRefresh: false }
const command: IpcCommand = 'control_task'

// @ts-expect-error inspect_video requires inputPath.
const missingInspectPath: IpcInvokeArgs<'inspect_video'> = {}
// @ts-expect-error forceRefresh is a boolean in the generated IPC manifest.
const invalidRefreshFlag: IpcInvokeArgs<'check_environment'> = { forceRefresh: 'false' }
// @ts-expect-error load_workbench_preset returns a nullable preset, not a number.
const invalidPresetResult: IpcInvokeResult<'load_workbench_preset'> = 1

describe('generated IPC contract types', () => {
  it('binds every command to its own argument and result shapes', () => {
    expect(inspectArgs.inputPath).toContain('input.mp4')
    expect(environmentArgs.forceRefresh).toBe(false)
    expect(command).toBe('control_task')
    expect(missingInspectPath).toEqual({})
    expect(invalidRefreshFlag.forceRefresh).toBe('false')
    expect(invalidPresetResult).toBe(1)
  })
})
