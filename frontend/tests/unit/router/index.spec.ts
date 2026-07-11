import { describe, expect, it } from 'vitest'

import { router } from '@/router'

describe('workbench router', () => {
  it('reuses the stage view with explicit preprocess and postprocess props', () => {
    const preprocess = router.getRoutes().find((route) => route.name === 'preprocess')
    const postprocess = router.getRoutes().find((route) => route.name === 'postprocess')

    expect(preprocess?.components?.default).toBe(postprocess?.components?.default)
    expect(preprocess?.props.default).toEqual({ stage: 'preprocess' })
    expect(postprocess?.props.default).toEqual({ stage: 'postprocess' })
  })
})
