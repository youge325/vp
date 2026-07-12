import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { isDeepStrictEqual } from 'node:util'
import { createTauriPage, isLocatorAdapter, navigateHome, resetAppState, waitForAppShell, type LocatorAdapter, type TauriPage } from './utils/wdio-tauri'

type TestContext = { tauriPage: TauriPage }
type TestBody = (context: TestContext) => Promise<void> | void

class SkipTest extends Error {
  constructor(message = 'Skipped by test.skip()') {
    super(message)
  }
}

let activePage: TauriPage | undefined

const mocha = () => globalThis as typeof globalThis & {
  describe: Mocha.SuiteFunction
  it: Mocha.TestFunction
  beforeEach: Mocha.HookFunction
  afterEach: Mocha.HookFunction
}

const currentPage = () => {
  if (!activePage) {
    throw new Error('Tauri page is not ready')
  }
  return activePage
}

mocha().beforeEach(async () => {
  activePage = createTauriPage()
  await waitForAppShell()
  await resetAppState()
  await navigateHome()
})

mocha().afterEach(async function () {
  const page = activePage
  activePage = undefined
  if (!page) {
    return
  }

  try {
    const coverage = await page.evaluate(() => (window as any).__coverage__ ?? null)
    if (coverage) {
      const outputDir = resolve(process.cwd(), '.nyc_output')
      mkdirSync(outputDir, { recursive: true })
      const testTitle = this.currentTest?.fullTitle().replace(/[^a-z0-9_-]+/gi, '-') ?? 'wdio-e2e'
      writeFileSync(resolve(outputDir, `${Date.now()}-${testTitle}.json`), JSON.stringify(coverage))
    }
  } catch {
    // Coverage is best-effort; assertion failures should stay focused on the spec.
  }
})

const runWithSkip = async (context: Mocha.Context, body: TestBody) => {
  try {
    await body({ tauriPage: currentPage() })
  } catch (error) {
    if (error instanceof SkipTest) {
      context.skip()
      return
    }
    throw error
  }
}

const skip = (...args: unknown[]) => {
  if (typeof args[0] === 'string' && typeof args[1] === 'function') {
    mocha().it.skip(args[0], args[1] as Mocha.Func)
    return
  }

  const condition = args.length === 0 ? true : Boolean(args[0])
  if (condition) {
    throw new SkipTest(typeof args[1] === 'string' ? args[1] : undefined)
  }
}

type TestApi = {
  (title: string, body: TestBody): void
  describe: Mocha.SuiteFunction
  beforeEach: (body: TestBody) => void
  skip: typeof skip
}

export const test: TestApi = Object.assign(
  (title: string, body: TestBody) => {
    mocha().it(title, async function () {
      await runWithSkip(this, body)
    })
  },
  {
    describe: mocha().describe,
    beforeEach: (body: TestBody) => {
      mocha().beforeEach(async function () {
        await runWithSkip(this, body)
      })
    },
    skip,
  },
)

type LocatorExpectationOptions = { timeout?: number }
type CheckedExpectationOptions = LocatorExpectationOptions & { checked?: boolean }

const pollLocator = async (assertion: () => Promise<void>, timeout = 5000) => {
  const deadline = Date.now() + timeout
  let lastError: unknown
  while (Date.now() <= deadline) {
    try {
      await assertion()
      return
    } catch (error) {
      lastError = error
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
  }
  throw lastError instanceof Error ? lastError : new Error('locator assertion timed out')
}

const makeLocatorExpect = (locator: LocatorAdapter, negate: boolean): any => {
  const assert = async (condition: boolean, message: string) => {
    if (negate ? condition : !condition) {
      throw new Error(message)
    }
  }

  const expectedTextMatches = (actual: string | null, expected: string | RegExp) => {
    const value = actual ?? ''
    return expected instanceof RegExp ? expected.test(value) : value === expected
  }

  const expectedTextContains = (actual: string | null, expected: string | RegExp) => {
    const value = actual ?? ''
    return expected instanceof RegExp ? expected.test(value) : value.includes(expected)
  }

  const api = {
    get not() {
      return makeLocatorExpect(locator, !negate)
    },
    async toBeVisible(options?: LocatorExpectationOptions) {
      await pollLocator(async () => assert(await locator.isVisible(), 'expected locator to be visible'), options?.timeout)
    },
    async toBeEnabled(options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const enabled = await locator.element().then((element) => element.isEnabled())
        await assert(enabled, 'expected locator to be enabled')
      }, options?.timeout)
    },
    async toBeDisabled(options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const enabled = await locator.element().then((element) => element.isEnabled())
        await assert(!enabled, 'expected locator to be disabled')
      }, options?.timeout)
    },
    async toBeChecked(options?: CheckedExpectationOptions) {
      const expected = options?.checked ?? true
      await pollLocator(async () => {
        const checked = await locator.isChecked()
        await assert(checked === expected, `expected locator ${expected ? 'to be checked' : 'not to be checked'}`)
      }, options?.timeout)
    },
    async toHaveText(expected: string | RegExp, options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const actual = await locator.textContent()
        await assert(expectedTextMatches(actual, expected), `expected text ${String(actual)} to equal ${String(expected)}`)
      }, options?.timeout)
    },
    async toContainText(expected: string | RegExp, options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const actual = await locator.textContent()
        await assert(expectedTextContains(actual, expected), `expected text ${String(actual)} to contain ${String(expected)}`)
      }, options?.timeout)
    },
    async toHaveCount(expected: number, options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const actual = await locator.count()
        await assert(actual === expected, `expected count ${actual} to equal ${expected}`)
      }, options?.timeout)
    },
    async toHaveAttribute(name: string, expected?: string | RegExp, options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const actual = await locator.getAttribute(name)
        if (expected === undefined) {
          await assert(actual !== null, `expected attribute ${name} to exist`)
          return
        }
        await assert(expectedTextMatches(actual, expected), `expected attribute ${name}=${String(actual)} to equal ${String(expected)}`)
      }, options?.timeout)
    },
    async toHaveClass(expected: string | RegExp, options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const actual = await locator.getAttribute('class')
        await assert(expectedTextContains(actual, expected), `expected class ${String(actual)} to match ${String(expected)}`)
      }, options?.timeout)
    },
    async toHaveValue(expected: string | RegExp, options?: LocatorExpectationOptions) {
      await pollLocator(async () => {
        const actual = await locator.inputValue()
        await assert(expectedTextMatches(actual, expected), `expected value ${String(actual)} to equal ${String(expected)}`)
      }, options?.timeout)
    },
  }

  return api
}

const format = (value: unknown) => {
  if (typeof value === 'string') {
    return JSON.stringify(value)
  }
  return JSON.stringify(value)
}

const unboxPrimitive = (value: unknown) => {
  const tag = Object.prototype.toString.call(value)
  if (tag === '[object String]' || tag === '[object Number]' || tag === '[object Boolean]') {
    return (value as { valueOf: () => unknown }).valueOf()
  }
  return value
}

const getProperty = (value: unknown, path: string) => {
  return path.split('.').reduce<unknown>((current, key) => {
    if (current === null || current === undefined) {
      return undefined
    }
    return (current as Record<string, unknown>)[key]
  }, value)
}

const makeValueExpect = (actual: unknown, negate: boolean): any => {
  const assert = (condition: boolean, message: string) => {
    if (negate ? condition : !condition) {
      throw new Error(message)
    }
  }

  const api = {
    get not() {
      return makeValueExpect(actual, !negate)
    },
    toBe(expected: unknown) {
      assert(
        Object.is(unboxPrimitive(actual), unboxPrimitive(expected)),
        `expected ${format(actual)} to be ${format(expected)}`,
      )
    },
    toEqual(expected: unknown) {
      assert(isDeepStrictEqual(actual, expected), `expected ${format(actual)} to equal ${format(expected)}`)
    },
    toHaveProperty(path: string, expected?: unknown) {
      const value = getProperty(actual, path)
      const exists = value !== undefined
      if (arguments.length === 1) {
        assert(exists, `expected ${format(actual)} to have property ${path}`)
        return
      }
      assert(exists && isDeepStrictEqual(value, expected), `expected property ${path} to equal ${format(expected)}`)
    },
    toBeGreaterThan(expected: number) {
      assert(Number(actual) > expected, `expected ${format(actual)} to be greater than ${expected}`)
    },
    toBeGreaterThanOrEqual(expected: number) {
      assert(Number(actual) >= expected, `expected ${format(actual)} to be greater than or equal to ${expected}`)
    },
    toBeLessThan(expected: number) {
      assert(Number(actual) < expected, `expected ${format(actual)} to be less than ${expected}`)
    },
    toBeTruthy() {
      assert(Boolean(actual), `expected ${format(actual)} to be truthy`)
    },
    toBeNull() {
      assert(actual === null, `expected ${format(actual)} to be null`)
    },
    toContain(expected: unknown) {
      const contains = typeof actual === 'string'
        ? actual.includes(String(expected))
        : Array.isArray(actual) && actual.some((item) => isDeepStrictEqual(item, expected))
      assert(contains, `expected ${format(actual)} to contain ${format(expected)}`)
    },
    toMatch(expected: string | RegExp) {
      const value = String(actual)
      assert(expected instanceof RegExp ? expected.test(value) : value.includes(expected), `expected ${format(actual)} to match ${String(expected)}`)
    },
    toBeCloseTo(expected: number, precision = 2) {
      const diff = Math.abs(Number(actual) - expected)
      assert(diff < 0.5 * 10 ** -precision, `expected ${format(actual)} to be close to ${expected}`)
    },
  }

  return api
}

export const expect = (actual: unknown) => {
  if (isLocatorAdapter(actual)) {
    return makeLocatorExpect(actual, false)
  }
  return makeValueExpect(actual, false)
}
