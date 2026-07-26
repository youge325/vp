import { spawnSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

export const E2E_FIXTURE_FILENAME = 'vp-e2e-test.mp4'

export function buildE2EFixtureArguments(outputPath) {
  return [
    '-f', 'lavfi',
    '-i', 'testsrc=duration=0.5:size=320x180:rate=10',
    '-f', 'lavfi',
    '-i', 'sine=frequency=1000:duration=0.5',
    '-shortest',
    '-pix_fmt', 'yuv420p',
    '-c:v', 'libx264',
    '-c:a', 'aac',
    outputPath,
    '-y',
  ]
}

export function generateE2EFixture(outputPath, ffmpegPath = process.env.VP_FFMPEG_PATH ?? 'ffmpeg') {
  const resolvedOutput = resolve(outputPath)
  mkdirSync(dirname(resolvedOutput), { recursive: true })
  const result = spawnSync(ffmpegPath, buildE2EFixtureArguments(resolvedOutput), {
    stdio: 'inherit',
    windowsHide: true,
  })
  if (result.error) {
    throw result.error
  }
  if (result.status !== 0) {
    throw new Error(`FFmpeg fixture generation failed with exit code ${result.status}`)
  }
  return resolvedOutput
}

const isMain = process.argv[1]
  && import.meta.url === pathToFileURL(resolve(process.argv[1])).href

if (isMain) {
  const outputPath = process.argv[2]
  if (!outputPath) {
    throw new Error('usage: node scripts/generate-e2e-fixture.mjs <output-path>')
  }
  process.stdout.write(`${generateE2EFixture(outputPath)}\n`)
}
