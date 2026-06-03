type TextMatcher = string | RegExp

interface LocatorOptions {
  hasText?: TextMatcher
  has?: LocatorAdapter
}

interface LocatorSegment {
  selector: string
  hasText?: TextMatcher
  has?: LocatorAdapter
  index?: number
}

export interface WaitForOptions {
  state?: 'attached' | 'detached' | 'visible' | 'hidden'
  timeout?: number
}

export interface TauriPage {
  locator: (selector: string, options?: LocatorOptions) => LocatorAdapter
  click: (selector: string) => Promise<void>
  evaluate: <T = unknown, A = unknown>(fn: (arg: A) => T | Promise<T>, arg?: A) => Promise<T>
  waitForFunction: <A = unknown>(
    fn: (arg: A) => unknown | Promise<unknown>,
    argOrOptions?: A | { timeout?: number; polling?: number },
    options?: { timeout?: number; polling?: number },
  ) => Promise<void>
  waitForTimeout: (ms: number) => Promise<void>
  keyboard: {
    press: (key: string) => Promise<void>
  }
}

type WdioElement = WebdriverIO.Element

const locatorBrand = Symbol('wdio-tauri-locator')

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

const getBrowser = () => {
  const wdioBrowser = (globalThis as { browser?: WebdriverIO.Browser }).browser
  if (!wdioBrowser) {
    throw new Error('WebDriverIO browser is not available')
  }
  return wdioBrowser
}

const normalizeSelector = (selector: string): LocatorSegment => {
  const hasTextMatch = selector.match(/:has-text\((['"])(.*?)\1\)/)
  if (!hasTextMatch) {
    return { selector }
  }

  const normalized = selector.replace(hasTextMatch[0], '').trim()
  return {
    selector: normalized.length > 0 ? normalized : '*',
    hasText: hasTextMatch[2],
  }
}

const matchesText = (text: string, matcher: TextMatcher) => {
  if (matcher instanceof RegExp) {
    return matcher.test(text)
  }
  return text.includes(matcher)
}

const stringifyValue = (value: unknown) => {
  if (typeof value === 'string') {
    return value
  }
  return JSON.stringify(value)
}

const readText = async (element: WdioElement) => {
  const text = await element.getText().catch(() => '')
  if (text.length > 0) {
    return text
  }
  return (await getBrowser().execute((node: Element) => node.textContent ?? '', element)) as string
}

const isElementVisible = async (element: WdioElement) => {
  return (await getBrowser().execute((node: Element) => {
    const style = window.getComputedStyle(node)
    const rect = node.getBoundingClientRect()
    return style.display !== 'none'
      && style.visibility !== 'hidden'
      && Number(style.opacity) !== 0
      && rect.width > 0
      && rect.height > 0
  }, element)) as boolean
}

const waitUntil = async (predicate: () => Promise<boolean>, timeout = 5000, message = 'condition was not met') => {
  const deadline = Date.now() + timeout
  let lastError: unknown

  while (Date.now() <= deadline) {
    try {
      if (await predicate()) {
        return
      }
    } catch (error) {
      lastError = error
    }
    await sleep(100)
  }

  const suffix = lastError instanceof Error ? `: ${lastError.message}` : ''
  throw new Error(`${message}${suffix}`)
}

export class LocatorAdapter {
  readonly [locatorBrand] = true

  constructor(
    private readonly segments: LocatorSegment[],
    private readonly index?: number,
  ) {}

  locator(selector: string, options?: LocatorOptions) {
    return new LocatorAdapter([...this.segmentsWithAppliedIndex(), toSegment(selector, options)])
  }

  filter(options: LocatorOptions) {
    const next = [...this.segments]
    const last = next[next.length - 1]
    next[next.length - 1] = {
      ...last,
      hasText: options.hasText ?? last.hasText,
      has: options.has ?? last.has,
    }
    return new LocatorAdapter(next, this.index)
  }

  first() {
    return new LocatorAdapter(this.segments, 0)
  }

  nth(index: number) {
    return new LocatorAdapter(this.segments, index)
  }

  last() {
    return new LocatorAdapter(this.segments, -1)
  }

  async count() {
    return (await this.resolve()).length
  }

  async allTextContents() {
    const elements = await this.resolve()
    return Promise.all(elements.map((element) => readText(element)))
  }

  async all() {
    const elements = await this.resolve()
    return elements.map((_, index) => this.nth(index))
  }

  async textContent() {
    const element = await this.element()
    return (await getBrowser().execute((node: Element) => node.textContent, element)) as string | null
  }

  async getAttribute(name: string) {
    return await this.element().then((element) => element.getAttribute(name))
  }

  async inputValue() {
    return await this.element().then((element) => element.getValue())
  }

  async isVisible() {
    try {
      const element = await this.element()
      return await isElementVisible(element)
    } catch {
      return false
    }
  }

  async isChecked() {
    try {
      const element = await this.element()
      return await element.isSelected()
    } catch {
      return false
    }
  }

  async click(_options?: { position?: { x: number; y: number } }) {
    await this.waitFor({ state: 'visible', timeout: 5000 })
    const element = await this.element()
    await getBrowser().execute((node: Element) => {
      const target = node as HTMLElement
      target.scrollIntoView({ block: 'center', inline: 'center' })
      target.click()
    }, element)
    await sleep(50)
  }

  async fill(value: string) {
    await this.waitFor({ state: 'visible', timeout: 5000 })
    const element = await this.element()
    const assigned = await getBrowser().execute((node: Element, nextValue: string) => {
      if (node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement) {
        node.focus()
        node.value = nextValue
        node.dispatchEvent(new Event('input', { bubbles: true }))
        node.dispatchEvent(new Event('change', { bubbles: true }))
        return true
      }
      return false
    }, element, value)
    if (!assigned) {
      await element.setValue(value)
    }
    await sleep(50)
  }

  async blur() {
    const element = await this.element()
    await getBrowser().execute((node: HTMLElement) => node.blur(), element)
  }

  async evaluate<T = unknown, A = unknown>(fn: (element: Element, arg: A) => T | Promise<T>, arg?: A) {
    const element = await this.element()
    const result = (await getBrowser().executeAsync(
      (node: Element, source: string, value: unknown, done: (payload: unknown) => void) => {
        const serializeError = (error: unknown) => {
          if (error instanceof Error) {
            return {
              message: error.message,
              stack: error.stack,
              name: error.name,
            }
          }
          return { message: String(error) }
        }

        try {
          const callback = (0, eval)(`(${source})`) as (element: Element, value: unknown) => unknown
          Promise.resolve(callback(node, value)).then(
            (evaluated) => done({ ok: true, value: evaluated }),
            (error) => done({ ok: false, error: serializeError(error) }),
          )
        } catch (error) {
          done({ ok: false, error: serializeError(error) })
        }
      },
      element,
      fn.toString(),
      arg,
    )) as { ok: true; value: unknown } | { ok: false; error: { message: string; stack?: string; name?: string } }

    if (!result.ok) {
      const failed = result as { ok: false; error: { message: string; stack?: string; name?: string } }
      const error = new Error(failed.error.message)
      error.name = failed.error.name ?? error.name
      error.stack = failed.error.stack ?? error.stack
      throw error
    }
    return result.value as Awaited<ReturnType<typeof fn>>
  }

  async selectOption(option: string | { label?: string; value?: string; index?: number }) {
    await this.waitFor({ state: 'attached', timeout: 5000 })
    const element = await this.element()
    if (typeof option === 'string') {
      await element.selectByAttribute('value', option)
      return
    }
    if (option.label !== undefined) {
      await element.selectByVisibleText(option.label)
      return
    }
    if (option.value !== undefined) {
      await element.selectByAttribute('value', option.value)
      return
    }
    if (option.index !== undefined) {
      await element.selectByIndex(option.index)
      return
    }
    throw new Error(`Unsupported selectOption payload: ${stringifyValue(option)}`)
  }

  async waitFor(options: WaitForOptions = {}) {
    const state = options.state ?? 'visible'
    const timeout = options.timeout ?? 5000
    await waitUntil(
      async () => {
        const elements = await this.resolve()
        if (state === 'attached') {
          return elements.length > 0
        }
        if (state === 'detached') {
          return elements.length === 0
        }
        if (state === 'visible') {
          return elements.length > 0 && (await isElementVisible(elements[0]))
        }
        if (elements.length === 0) {
          return true
        }
        return !(await isElementVisible(elements[0]))
      },
      timeout,
      `locator did not reach state "${state}"`,
    )
  }

  async element() {
    const elements = await this.resolve()
    if (elements.length === 0) {
      throw new Error(`No element matched locator ${this.toString()}`)
    }
    return elements[0]
  }

  async resolveWithin(root: WdioElement) {
    return this.resolveFrom([root], false)
  }

  async resolve() {
    return this.resolveFrom([getBrowser()], true)
  }

  toString() {
    return this.segments.map((segment) => segment.selector).join(' >> ')
  }

  private async resolveFrom(roots: Array<WebdriverIO.Browser | WdioElement>, applyIndex: boolean) {
    let current: WdioElement[] = []
    let activeRoots = roots

    for (const segment of this.segments) {
      const next: WdioElement[] = []
      for (const root of activeRoots) {
        let elements: WdioElement[]
        try {
          elements = (await root.$$(segment.selector)) as unknown as WdioElement[]
        } catch {
          continue
        }
        for (const element of elements) {
          try {
            if (segment.hasText !== undefined && !matchesText(await readText(element), segment.hasText)) {
              continue
            }
            if (segment.has !== undefined && (await segment.has.resolveWithin(element)).length === 0) {
              continue
            }
          } catch {
            continue
          }
          next.push(element)
        }
      }
      current = next
      if (segment.index !== undefined) {
        const resolvedIndex = segment.index < 0 ? current.length + segment.index : segment.index
        current = current[resolvedIndex] ? [current[resolvedIndex]] : []
      }
      activeRoots = current
    }

    if (!applyIndex || this.index === undefined) {
      return current
    }
    const resolvedIndex = this.index < 0 ? current.length + this.index : this.index
    const element = current[resolvedIndex]
    return element ? [element] : []
  }

  private segmentsWithAppliedIndex() {
    if (this.index === undefined || this.segments.length === 0) {
      return this.segments
    }

    const next = [...this.segments]
    const last = next[next.length - 1]
    next[next.length - 1] = { ...last, index: this.index }
    return next
  }
}

const toSegment = (selector: string, options?: LocatorOptions): LocatorSegment => {
  const segment = normalizeSelector(selector)
  return {
    ...segment,
    hasText: options?.hasText ?? segment.hasText,
    has: options?.has,
  }
}

export const isLocatorAdapter = (value: unknown): value is LocatorAdapter => {
  return Boolean(value && typeof value === 'object' && locatorBrand in value)
}

export const createTauriPage = (): TauriPage => ({
  locator: (selector, options) => new LocatorAdapter([toSegment(selector, options)]),
  click: async (selector) => {
    await new LocatorAdapter([toSegment(selector)]).click()
  },
  evaluate: async (fn, arg) => {
    const result = (await getBrowser().executeAsync(
      (source: string, value: unknown, done: (payload: unknown) => void) => {
        const serializeError = (error: unknown) => {
          if (error instanceof Error) {
            return {
              message: error.message,
              stack: error.stack,
              name: error.name,
            }
          }
          return { message: String(error) }
        }

        try {
          const callback = (0, eval)(`(${source})`) as (value: unknown) => unknown
          Promise.resolve(callback(value)).then(
            (evaluated) => done({ ok: true, value: evaluated }),
            (error) => done({ ok: false, error: serializeError(error) }),
          )
        } catch (error) {
          done({ ok: false, error: serializeError(error) })
        }
      },
      fn.toString(),
      arg,
    )) as { ok: true; value: unknown } | { ok: false; error: { message: string; stack?: string; name?: string } }

    if (!result.ok) {
      const failed = result as { ok: false; error: { message: string; stack?: string; name?: string } }
      const error = new Error(failed.error.message)
      error.name = failed.error.name ?? error.name
      error.stack = failed.error.stack ?? error.stack
      throw error
    }
    return result.value as Awaited<ReturnType<typeof fn>>
  },
  waitForFunction: async (fn, argOrOptions, options) => {
    const maybeOptions = options ?? (isWaitForOptions(argOrOptions) ? argOrOptions : undefined)
    const arg = options || !isWaitForOptions(argOrOptions) ? (argOrOptions as unknown) : undefined
    const page = createTauriPage()
    await waitUntil(
      async () => Boolean(await page.evaluate(fn as (value: unknown) => unknown, arg)),
      maybeOptions?.timeout ?? 5000,
      'waitForFunction timed out',
    )
  },
  waitForTimeout: sleep,
  keyboard: {
    press: async (key) => {
      await getBrowser().keys(key)
    },
  },
})

const isWaitForOptions = (value: unknown): value is { timeout?: number; polling?: number } => {
  return Boolean(value && typeof value === 'object' && ('timeout' in value || 'polling' in value))
}

export const waitForAppShell = async (timeout = 15000) => {
  await createTauriPage().locator('[data-testid="app-shell"]').waitFor({ state: 'visible', timeout })
}

export const resetAppState = async () => {
  await getBrowser().executeAsync((done: (payload: { ok: boolean; error?: string }) => void) => {
    const clone = (value: unknown) => JSON.parse(JSON.stringify(value))
    const restore = (target: unknown, source: unknown): unknown => {
      if (Array.isArray(source)) {
        if (Array.isArray(target)) {
          target.splice(0, target.length, ...clone(source))
          return target
        }
        return clone(source)
      }

      if (source && typeof source === 'object') {
        if (!target || typeof target !== 'object' || Array.isArray(target)) {
          return clone(source)
        }

        const targetRecord = target as Record<string, unknown>
        const sourceRecord = source as Record<string, unknown>
        for (const key of Object.keys(targetRecord)) {
          if (!(key in sourceRecord)) {
            delete targetRecord[key]
          }
        }
        for (const [key, value] of Object.entries(sourceRecord)) {
          targetRecord[key] = restore(targetRecord[key], value)
        }
        return targetRecord
      }

      return source
    }

    const finish = () => {
      try {
        const root = document.querySelector('#app') as HTMLElement & { __vue_app__?: unknown } | null
        const vueApp = root?.__vue_app__ as { config?: { globalProperties?: { $pinia?: { state?: { value?: Record<string, unknown> } } } } } | undefined
        const state = vueApp?.config?.globalProperties?.$pinia?.state?.value
        if (!state) {
          done({ ok: false, error: 'Pinia state is not available' })
          return
        }

        const win = window as typeof window & { __VP_E2E_INITIAL_PINIA_STATE?: Record<string, unknown>; __E2E_EVENTS?: unknown[]; __E2E_UNLISTENERS?: unknown[] }
        if (!win.__VP_E2E_INITIAL_PINIA_STATE) {
          win.__VP_E2E_INITIAL_PINIA_STATE = clone(state) as Record<string, unknown>
        }
        const initial = clone(win.__VP_E2E_INITIAL_PINIA_STATE) as Record<string, unknown>

        for (const key of Object.keys(state)) {
          if (!(key in initial)) {
            delete state[key]
          }
        }
        for (const [key, value] of Object.entries(initial)) {
          state[key] = restore(state[key], value)
        }
        win.__E2E_EVENTS = []
        win.__E2E_UNLISTENERS = []
        done({ ok: true })
      } catch (error) {
        done({ ok: false, error: error instanceof Error ? error.message : String(error) })
      }
    }

    const win = window as typeof window & { __E2E_UNLISTENERS?: Array<() => Promise<void> | void> }
    const unlisteners = win.__E2E_UNLISTENERS ?? []
    Promise.allSettled(unlisteners.map((unlisten) => unlisten())).finally(finish)
  }).then((result) => {
    if (!result.ok) {
      throw new Error(result.error ?? 'failed to reset app state')
    }
  })
}

export const navigateHome = async () => {
  await getBrowser().executeAsync((done: () => void) => {
    if (window.location.hash === '#/home') {
      done()
      return
    }

    window.location.hash = '#/home'
    setTimeout(done, 0)
  })
  await createTauriPage().locator('[data-testid="home-module"]').waitFor({ state: 'visible', timeout: 5000 })
}
