import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'

import ResumeConflictDialog from '@/components/ResumeConflictDialog.vue'

describe('ResumeConflictDialog', () => {
  it('renders resumable progress from the domain projection', async () => {
    const wrapper = mount(ResumeConflictDialog, {
      props: {
        descriptor: {
          kind: 'final_exists_with_resume',
          outputPath: 'D:/out.mp4',
          progress: {
            completedChunks: 2,
            completedOutputFrames: 120,
            totalOutputFrames: 240,
          },
        },
      },
      attachTo: document.body,
    })
    await nextTick()

    expect(wrapper.text()).toContain('已找到 2 段缓存（第 120 / 240 帧）')
    expect(wrapper.text()).toContain('继续续传')
    expect(wrapper.text()).toContain('D:/out.mp4')
    wrapper.unmount()
  })

  it('renders overwrite actions for a non-resumable conflict', async () => {
    const wrapper = mount(ResumeConflictDialog, {
      props: {
        descriptor: {
          kind: 'final_exists_only',
          outputPath: 'D:/out.mp4',
          progress: {
            completedChunks: 0,
            completedOutputFrames: 0,
            totalOutputFrames: 0,
          },
        },
      },
      attachTo: document.body,
    })
    await nextTick()

    expect(wrapper.text()).toContain('输出文件已存在')
    expect(wrapper.text()).toContain('覆盖')
    expect(wrapper.text()).not.toContain('继续续传')
    wrapper.unmount()
  })
})
