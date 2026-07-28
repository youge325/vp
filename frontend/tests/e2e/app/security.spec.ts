import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test } from '../fixtures'

test.describe('Desktop security boundary', () => {
  test('blocks inline scripts under the packaged CSP', async ({ tauriPage }) => {
    const result = await tauriPage.evaluate(async () => {
      return await new Promise<{ executed: boolean, violated: boolean }>((resolveResult) => {
        const marker = '__VP_UNSAFE_INLINE_EXECUTED__'
        let violated = false
        const listener = () => {
          violated = true
        }
        document.addEventListener('securitypolicyviolation', listener, { once: true })
        const script = document.createElement('script')
        script.textContent = `window.${marker} = true`
        document.head.append(script)
        window.setTimeout(() => {
          resolveResult({
            executed: Boolean((window as any)[marker]),
            violated,
          })
        }, 100)
      })
    })

    expect(result.executed).toBe(false)
    expect(result.violated).toBe(true)
  })

  test('ships one local-only capability scoped to the main window', () => {
    const capability = JSON.parse(readFileSync(
      resolve(process.cwd(), 'src-tauri', 'capabilities', 'default.json'),
      'utf8',
    ))
    expect(capability.local).toBe(true)
    expect(capability.windows).toEqual(['main'])
    expect(capability.remote).toBe(undefined)

    const config = JSON.parse(readFileSync(
      resolve(process.cwd(), 'src-tauri', 'tauri.conf.json'),
      'utf8',
    ))
    expect(config.app.security.capabilities).toEqual(['default'])
    expect(config.app.security.csp).toContain("script-src 'self'")
    expect(config.app.security.csp).toContain("object-src 'none'")
    expect(config.app.security.csp).toContain("frame-src 'none'")
  })
})
