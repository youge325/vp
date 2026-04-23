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
      '解码',
      '增强',
      '编码',
      '渲染',
    ])
  })

  it('keeps stable paths and icons for each module', () => {
    expect(WORKBENCH_MODULES.map((module) => module.path)).toEqual([
      '/home',
      '/input',
      '/decode',
      '/enhance',
      '/encode',
      '/render',
    ])
    expect(WORKBENCH_MODULES.every((module) => Boolean(module.icon))).toBe(true)
  })

  it('keeps only the root redirect plus the six formal module routes', async () => {
    const routePaths = router
      .getRoutes()
      .map((route) => route.path)
      .filter((path) =>
        ['/', '/home', '/input', '/decode', '/enhance', '/encode', '/render'].includes(path),
      )
      .sort()

    expect(routePaths).toEqual(['/', '/decode', '/encode', '/enhance', '/home', '/input', '/render'])

    await router.push('/')
    expect(router.currentRoute.value.fullPath).toBe('/home')
  })
})
