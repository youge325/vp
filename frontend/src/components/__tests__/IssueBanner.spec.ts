import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import IssueBanner from '../IssueBanner.vue'
import { TASK_ERROR_CODES } from '@/types/protocol'
import type { TaskError } from '@/types/domain/media'

function makeIssue(message: string): TaskError {
  return {
    code: TASK_ERROR_CODES.Unknown,
    message,
    details: null,
  }
}

describe('IssueBanner', () => {
  it('renders nothing when issue is null', () => {
    const wrapper = mount(IssueBanner, {
      props: { issue: null, title: '导入失败' },
    })
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toBe('')
  })

  it('renders title and message when issue is present', () => {
    const wrapper = mount(IssueBanner, {
      props: { issue: makeIssue('文件丢失'), title: '导入失败' },
    })
    const banner = wrapper.find('[role="alert"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('导入失败')
    expect(banner.text()).toContain('文件丢失')
  })

  it('applies warning variant class when variant=warning', () => {
    const wrapper = mount(IssueBanner, {
      props: { issue: makeIssue('low disk'), title: '空间告警', variant: 'warning' },
    })
    const banner = wrapper.find('[role="alert"]')
    expect(banner.classes()).toContain('info-banner-warning')
    expect(banner.classes()).not.toContain('info-banner-danger')
  })

  it('defaults to danger variant when variant is unspecified', () => {
    const wrapper = mount(IssueBanner, {
      props: { issue: makeIssue('boom'), title: 'X' },
    })
    const banner = wrapper.find('[role="alert"]')
    expect(banner.classes()).toContain('info-banner-danger')
  })
})
