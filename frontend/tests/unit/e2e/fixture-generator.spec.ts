import {
  E2E_FIXTURE_FILENAME,
  buildE2EFixtureArguments,
} from '../../../scripts/generate-e2e-fixture.mjs'

describe('E2E media fixture', () => {
  it('uses the shared small video and audio profile', () => {
    const args = buildE2EFixtureArguments(`C:/tmp/${E2E_FIXTURE_FILENAME}`)
    expect(args).toContain('testsrc=duration=0.5:size=320x180:rate=10')
    expect(args).toContain('sine=frequency=1000:duration=0.5')
    expect(args).toContain('-shortest')
    expect(args.at(-2)).toBe(`C:/tmp/${E2E_FIXTURE_FILENAME}`)
  })
})
