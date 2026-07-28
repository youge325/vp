import { randomUUID } from 'node:crypto'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const sanitize = (value: string) => value.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '')

export const taskInputPath = () => process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'

export const createTaskOutputDir = (label: string) => {
  const root = process.env.VP_E2E_OUTPUT_DIR ?? 'C:/tmp/vp-e2e-output'
  const dir = resolve(root, `${sanitize(label)}-${process.pid}-${randomUUID()}`)
  mkdirSync(dir, { recursive: true })
  return dir
}
