import { expect, test } from 'claude-code/testing'

const NOW = Date.parse('2026-11-03T12:00:00Z')
const LIMITS = [
  { kind: 'five_hour', percentUsed: 23.5, resetsAt: '2026-11-03T14:05:00Z' },
  { kind: 'seven_day', percentUsed: 61, resetsAt: '2026-11-06T09:00:00Z' },
]
const PANE = {
  plugin: 'usage-meter',
  component: 'Pane',
  requestId: 'usage-meter',
  props: { title: 'Plan usage', isFocused: false, bodyColumns: 40, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

// Nothing sits beneath the plugin: each hook here stands for the engine.
function engine(on: any, limits: unknown[] | (() => unknown[]), toasts: string[] = [], statuses: (string | undefined)[] = []) {
  on('command.register', () => ({ value: { command: 'usage-meter' } }))
  on('tool.register', () => ({ value: { tool: 'mcp__usage-meter__usage' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('session.usage', () => ({ value: { startedAt: NOW - 3_600_000, context: {}, rateLimits: typeof limits === 'function' ? limits() : limits, cost: { usd: 12.34 } } }))
  on('clock.now', () => ({ value: NOW }))
  on('clock.every', () => ({ value: undefined })) // the minute tick: never fires here
  on('session.measure', (_: unknown, e: { changed: string[] }) => ({ changed: e.changed }))
  on('ui.toast', (_: unknown, e: { text: string }) => (toasts.push(e.text), { value: undefined }))
  on('ui.status', (_: unknown, e: { text?: string }) => (statuses.push(e.text), { value: undefined }))
}

test('the tool reads the windows, the cost and when each resets', async ($, on) => {
  const statuses: (string | undefined)[] = []
  engine(on, LIMITS, [], statuses)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const r = await $.tool.call({ tool: 'mcp__usage-meter__usage' } as any)
  const text = String((r as { result?: unknown }).result)
  expect(text).toContain('5-hour: 23.5% used, resets in 2h 05m')
  expect(text).toContain('Weekly: 61% used, resets in 2d 21h')
  expect(text).toContain('$12.34')
  expect(statuses.at(-1)).toBe('5h 24% · 7d 61%')
})

test('the pane draws both windows on every surface', async ($, on) => {
  engine(on, LIMITS)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  for (const surface of ['terminal', 'desktop', 'vscode', 'mobile'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /^Weekly/ }))?.text).toBe('Weekly 61%')
    expect((await ui.find({ type: 'Text', text: /resets in 2h 05m/ }))?.text).toContain('Tue 14:05 UTC')
    await ui.unmount()
  }
})

test('a weekly threshold is toasted once, and a higher one again', async ($, on) => {
  const toasts: string[] = []
  let limits: unknown[] = [{ kind: 'seven_day', percentUsed: 76, resetsAt: '2026-11-06T09:00:00Z' }]
  engine(on, () => limits, toasts)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  expect(toasts.length).toBe(1)
  expect(toasts[0]).toContain('passed 75%')
  await $.session.measure({ context: {}, rateLimits: limits, changed: ['rateLimits'] } as any)
  expect(toasts.length).toBe(1) // the same level again: no second toast
  limits = [{ kind: 'seven_day', percentUsed: 91, resetsAt: '2026-11-06T09:00:00Z' }]
  await $.session.measure({ context: {}, rateLimits: limits, changed: ['rateLimits'] } as any)
  expect(toasts.length).toBe(2)
  expect(toasts[1]).toContain('passed 90%')
})

test('with no reading yet the pane says so', async ($, on) => {
  engine(on, [])
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text' }))?.text).toContain('No reading yet')
  await ui.unmount()
})
