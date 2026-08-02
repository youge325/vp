import type { Browser as WdioBrowser, Element as WdioElement } from 'webdriverio'

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

interface WaitForOptions {
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

const locatorBrand = Symbol('wdio-tauri-locator')

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

const getBrowser = () => {
  const wdioBrowser = (globalThis as { browser?: WdioBrowser }).browser
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

const readTexts = async (elements: WdioElement[]) => {
  if (elements.length === 0) {
    return []
  }
  try {
    return (await getBrowser().execute((nodes: Element[]) => nodes.map((node) => {
      const renderedText = node instanceof HTMLElement ? node.innerText : ''
      return renderedText || node.textContent || ''
    }), elements)) as string[]
  } catch {
    return await Promise.all(elements.map((element) => readText(element)))
  }
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

interface SerializedBrowserError {
  message: string
  stack?: string
  name?: string
}

type SerializedBrowserResult =
  | { ok: true; value: unknown }
  | { ok: false; error: SerializedBrowserError }

const executeSerializedCallback = (
  source: string,
  args: unknown[],
  done: (payload?: unknown) => void,
) => {
  const serializeError = (error: unknown): SerializedBrowserError => {
    if (
      error instanceof Error
      || (
        typeof error === 'object'
        && error !== null
        && typeof (error as { message?: unknown }).message === 'string'
      )
    ) {
      const value = error as { message: string; stack?: string; name?: string }
      return {
        message: value.message,
        stack: value.stack,
        name: value.name,
      }
    }
    const message = typeof error === 'object' && error !== null
      ? JSON.stringify(error)
      : String(error)
    return { message }
  }

  try {
    const callback = (0, eval)(`(${source})`) as (...values: unknown[]) => unknown
    Promise.resolve(callback(...args)).then(
      (value) => done({ ok: true, value }),
      (error) => done({ ok: false, error: serializeError(error) }),
    )
  } catch (error) {
    done({ ok: false, error: serializeError(error) })
  }
}

const unwrapBrowserResult = <T>(result: SerializedBrowserResult): T => {
  if (result.ok === true) {
    return result.value as T
  }

  const error = new Error(result.error.message)
  error.name = result.error.name ?? error.name
  error.stack = result.error.stack ?? error.stack
  throw error
}

const evaluateBrowserCallback = async <T, Args extends unknown[] = unknown[]>(
  callback: (...args: Args) => unknown,
  ...args: Args
): Promise<T> => {
  const result = await getBrowser().executeAsync(
    executeSerializedCallback,
    callback.toString(),
    args,
  ) as SerializedBrowserResult
  return unwrapBrowserResult<T>(result)
}

export class LocatorAdapter {
  readonly [locatorBrand] = true
  private readonly segments: LocatorSegment[]
  private readonly index?: number

  constructor(segments: LocatorSegment[], index?: number) {
    this.segments = segments
    this.index = index
  }

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
    return await readTexts(elements)
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
    await getBrowser().executeAsync((node: Element, done: () => void) => {
      const target = node as HTMLElement
      target.scrollIntoView({ block: 'center', inline: 'center' })
      target.click()
      requestAnimationFrame(() => done())
    }, element)
  }

  async fill(value: string) {
    await this.waitFor({ state: 'visible', timeout: 5000 })
    const element = await this.element()
    const assigned = await getBrowser().executeAsync((
      node: Element,
      nextValue: string,
      done: (value: boolean) => void,
    ) => {
      if (node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement) {
        node.focus()
        node.value = nextValue
        node.dispatchEvent(new Event('input', { bubbles: true }))
        node.dispatchEvent(new Event('change', { bubbles: true }))
        requestAnimationFrame(() => done(true))
        return
      }
      done(false)
    }, element, value)
    if (!assigned) {
      await element.setValue(value)
      await getBrowser().executeAsync((done: () => void) => requestAnimationFrame(() => done()))
    }
  }

  async blur() {
    const element = await this.element()
    await getBrowser().execute((node: HTMLElement) => node.blur(), element)
  }

  async evaluate<T = unknown, A = unknown>(fn: (element: Element, arg: A) => T | Promise<T>, arg?: A) {
    const element = await this.element()
    return await evaluateBrowserCallback<
      Awaited<ReturnType<typeof fn>>,
      [WdioElement, A | undefined]
    >(
      fn as unknown as (element: WdioElement, arg: A | undefined) => T | Promise<T>,
      element,
      arg,
    )
  }

  async selectOption(option: string | { label?: string; value?: string; index?: number }) {
    await this.waitFor({ state: 'attached', timeout: 5000 })
    const element = await this.element()
    if (typeof option === 'string') {
      await element.selectByAttribute('value', option)
    } else if (option.label !== undefined) {
      await element.selectByVisibleText(option.label)
    } else if (option.value !== undefined) {
      await element.selectByAttribute('value', option.value)
    } else if (option.index !== undefined) {
      await element.selectByIndex(option.index)
    } else {
      throw new Error(`Unsupported selectOption payload: ${stringifyValue(option)}`)
    }
    await getBrowser().executeAsync((done: () => void) => requestAnimationFrame(() => done()))
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

  private async resolveFrom(roots: Array<WdioBrowser | WdioElement>, applyIndex: boolean) {
    let current: WdioElement[] = []
    let activeRoots = roots

    for (const segment of this.segments) {
      const next: WdioElement[] = []
      for (const root of activeRoots) {
        let elements: WdioElement[]
        try {
          const pendingElements = root.$$(segment.selector) as unknown as PromiseLike<ArrayLike<WdioElement>>
          elements = Array.from(
            await pendingElements,
          )
        } catch {
          continue
        }
        let matchingElements = elements
        if (segment.hasText !== undefined) {
          const texts = await readTexts(elements)
          matchingElements = elements.filter((_, index) => matchesText(texts[index] ?? '', segment.hasText!))
        }
        for (const element of matchingElements) {
          try {
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
    return await evaluateBrowserCallback<
      Awaited<ReturnType<typeof fn>>,
      [typeof arg]
    >(fn as (value: typeof arg) => ReturnType<typeof fn>, arg)
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

interface AppBootstrapStatus {
  piniaAvailable: boolean
  isBootstrapping: boolean
  isChecking: boolean
  presetPersistenceReady: boolean
}

export const isAppBootstrapReady = (status: AppBootstrapStatus) => {
  return status.piniaAvailable
    && !status.isBootstrapping
    && !status.isChecking
    && status.presetPersistenceReady
}

const readAppBootstrapStatus = async (): Promise<AppBootstrapStatus> => {
  return await getBrowser().execute(() => {
    const root = document.querySelector('#app') as HTMLElement & { __vue_app__?: unknown } | null
    const vueApp = root?.__vue_app__ as {
      config?: { globalProperties?: { $pinia?: { state?: { value?: Record<string, unknown> } } } }
    } | undefined
    const state = vueApp?.config?.globalProperties?.$pinia?.state?.value as {
      env?: { env?: { isBootstrapping?: boolean; isChecking?: boolean } }
      preset?: { presetPersistenceReady?: boolean }
    } | undefined
    return {
      piniaAvailable: Boolean(state),
      isBootstrapping: state?.env?.env?.isBootstrapping ?? true,
      isChecking: state?.env?.env?.isChecking ?? true,
      presetPersistenceReady: state?.preset?.presetPersistenceReady ?? false,
    }
  }) as AppBootstrapStatus
}

export const waitForAppBootstrap = async (timeout = 60000) => {
  await waitUntil(
    async () => isAppBootstrapReady(await readAppBootstrapStatus()),
    timeout,
    'application bootstrap did not complete',
  )
}

interface AppStateWindow extends Window {
  __VP_E2E_INITIAL_PINIA_STATE?: Record<string, unknown>
  __E2E_EVENTS?: unknown[]
  __E2E_UNLISTENERS?: Array<() => Promise<void> | void>
}

const runPiniaOperation = async (
  source: string,
  storeId: string | null,
  argument: unknown,
) => {
  const root = document.querySelector('#app') as HTMLElement & { __vue_app__?: unknown } | null
  const vueApp = root?.__vue_app__ as {
    config?: {
      globalProperties?: {
        $pinia?: {
          state?: { value?: Record<string, unknown> }
          _s?: Map<string, Record<string, unknown>>
        }
      }
    }
  } | undefined
  const pinia = vueApp?.config?.globalProperties?.$pinia
  const target = storeId === null ? pinia?.state?.value : pinia?._s?.get(storeId)
  if (!target) {
    throw new Error(storeId === null ? 'Pinia state is not available' : `Pinia store is not available: ${storeId}`)
  }

  const operation = (0, eval)(`(${source})`) as (
    value: Record<string, unknown>,
    win: AppStateWindow,
    argument: unknown,
  ) => unknown
  return await operation(target, window as AppStateWindow, argument)
}

export const withPiniaState = async <T, A = undefined>(
  operation: (
    state: Record<string, unknown>,
    win: AppStateWindow,
    argument: A,
  ) => T | Promise<T>,
  argument?: A,
): Promise<T> => {
  return await evaluateBrowserCallback<T, [string, null, A | undefined]>(
    runPiniaOperation,
    operation.toString(),
    null,
    argument,
  )
}

export const withPiniaStore = async <T, A = undefined>(
  storeId: string,
  operation: (
    store: Record<string, unknown>,
    win: AppStateWindow,
    argument: A,
  ) => T | Promise<T>,
  argument?: A,
): Promise<T> => {
  return await evaluateBrowserCallback<T, [string, string, A | undefined]>(
    runPiniaOperation,
    operation.toString(),
    storeId,
    argument,
  )
}

export const captureAppStateBaseline = async () => {
  await withPiniaState((state, win) => {
    const clone = (value: unknown) => JSON.parse(JSON.stringify(value))
    win.__VP_E2E_INITIAL_PINIA_STATE = clone(state) as Record<string, unknown>
    win.__E2E_EVENTS = []
    win.__E2E_UNLISTENERS = []
  })
}

export const resetAppState = async () => {
  await withPiniaState(async (state, win) => {
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

    const unlisteners = win.__E2E_UNLISTENERS ?? []
    await Promise.allSettled(unlisteners.map((unlisten) => Promise.resolve().then(unlisten)))

    if (!win.__VP_E2E_INITIAL_PINIA_STATE) {
      throw new Error('Pinia state baseline is not available')
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
