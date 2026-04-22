import { beforeEach, describe, expect, it } from 'vitest'
import { WORKBENCH_MODULES } from '@/lib/workflow'
import { router } from '@/router'

describe('workflow routes', () => {
  beforeEach(async () => {
    await router.push('/home')
  })

  it('exposes six workbench modules', () => {
    expect(WORKBENCH_MODULES).toHaveLength(6)
    expect(WORKBENCH_MODULES.map((module) => module.title)).toEqual([
      '主页',
      '输入',
      '增强',
      '编码',
      '渲染',
      '预览',
    ])
  })

  it('keeps stable paths and icons for each module', () => {
    expect(WORKBENCH_MODULES.map((module) => module.path)).toEqual([
      '/home',
      '/input',
      '/enhance',
      '/encode',
      '/render',
      '/preview',
    ])
    expect(WORKBENCH_MODULES.every((module) => Boolean(module.icon))).toBe(true)
  })

  it('redirects legacy routes into the new module layout', async () => {
    const redirects = [
      ['/', '/home'],
      ['/overview', '/home'],
      ['/prepare', '/home'],
      ['/source', '/input'],
      ['/interpolation', '/enhance?section=interpolation'],
      ['/super-resolution', '/enhance?section=super-resolution'],
      ['/anime', '/enhance?section=anime'],
      ['/format', '/encode'],
      ['/deliver', '/encode'],
      ['/results', '/render'],
      ['/preview', '/preview'],
    ] as const

    for (const [from, to] of redirects) {
      await router.push(from)
      expect(router.currentRoute.value.fullPath).toBe(to)
    }
  })
})
