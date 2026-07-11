import { describe, expect, it } from 'vitest'

import { router } from '@/router'
import { WORKBENCH_MODULES } from '@/views/registry'

describe('workbench router', () => {
  it('reuses the stage view with explicit preprocess and postprocess props', () => {
    const preprocess = router.getRoutes().find((route) => route.name === 'preprocess')
    const postprocess = router.getRoutes().find((route) => route.name === 'postprocess')

    expect(preprocess?.components?.default).toBe(postprocess?.components?.default)
    expect(preprocess?.props.default).toEqual({ stage: 'preprocess' })
    expect(postprocess?.props.default).toEqual({ stage: 'postprocess' })
  })

  it('derives every module route from the workbench registry', () => {
    for (const module of WORKBENCH_MODULES) {
      const route = router.getRoutes().find((candidate) => candidate.name === module.key)

      expect(route?.path).toBe(module.path)
      expect(route?.meta.module).toBe(module)
    }
  })
})
