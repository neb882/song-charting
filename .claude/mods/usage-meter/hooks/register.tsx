import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, SessionRateLimit } from 'claude-code'

import type { Reading, Window } from '../types'

const PANE = 'usage-meter'
const TITLE = 'Plan usage'
const LABELS: Record<string, string> = { five_hour: '5-hour', seven_day: 'Weekly', spend_limit: 'Spend limit' }
const WEEKLY_WARN = [50, 75, 90] // a toast as the weekly window crosses each, once per week

// Change a tag when its value's fields change: an older stored value then reads as the initial one.
const reading = atom({ plugin: 'usage-meter', key: 'reading' } as const, null, { shape: 'reading-1' })
const warned = atom({ plugin: 'usage-meter', key: 'warned' } as const, null, { shape: 'warned-1' })
const tick = atom({ plugin: 'usage-meter', key: 'tick' } as const, 0)

const label = (kind: string) => LABELS[kind] ?? kind

/** "2h 05m", "3d 4h", "now": how long until an ISO time, from `now` (ms). */
function until(iso: string | undefined, now: number): string {
  if (!iso) return 'reset time unknown'
  const ms = Date.parse(iso) - now
  if (!Number.isFinite(ms)) return 'reset time unknown'
  if (ms <= 0) return 'resets now'
  const m = Math.floor(ms / 60_000)
  const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60
  return `resets in ${d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h ${String(mm).padStart(2, '0')}m` : `${mm}m`}`
}

/** The reset time as UTC, "Wed 14:00 UTC" (the module has no time zone of the person's). */
function at(iso: string | undefined): string {
  const t = iso ? Date.parse(iso) : NaN
  if (!Number.isFinite(t)) return ''
  const d = new Date(t)
  const day = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getUTCDay()]
  return `${day} ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')} UTC`
}

const windowsOf = (limits: readonly SessionRateLimit[]): Window[] =>
  limits.map(l => ({ kind: l.kind, percentUsed: l.percentUsed, resetsAt: l.resetsAt }))

/** One line per window, for the tool's answer and the status line. */
function summary(r: Reading | null, now: number): string {
  if (!r || r.windows.length === 0)
    return 'No usage reading yet: the engine reports the plan windows with each API response on a subscription.'
  const lines = r.windows.map(
    w => `${label(w.kind)}: ${w.percentUsed}% used, ${until(w.resetsAt, now)}${w.resetsAt ? ` (${w.resetsAt})` : ''}`,
  )
  if (r.costUsd !== undefined) lines.push(`This session's cost so far: $${r.costUsd.toFixed(2)} at API prices`)
  lines.push(`Read ${Math.max(0, Math.round((now - r.at) / 60_000))} min ago.`)
  return lines.join('\n')
}

const statusText = (r: Reading | null) =>
  r && r.windows.length
    ? r.windows.map(w => `${w.kind === 'five_hour' ? '5h' : w.kind === 'seven_day' ? '7d' : label(w.kind)} ${Math.round(w.percentUsed)}%`).join(' · ')
    : undefined

/** Take a reading, store it, and update the status line and the weekly toasts. */
async function record($: EngineInterface, limits: readonly SessionRateLimit[], costUsd?: number) {
  const now = await $.clock.now()
  const r: Reading = { at: now, windows: windowsOf(limits), costUsd }
  if (r.windows.length) await update($, reading, () => r)
  const shown = r.windows.length ? r : await read($, reading)
  $.ui.status(statusText(shown))
  const week = r.windows.find(w => w.kind === 'seven_day')
  if (week) {
    const level = [...WEEKLY_WARN].reverse().find(p => week.percentUsed >= p) ?? 0
    const before = await read($, warned)
    const same = before && before.resetsAt === (week.resetsAt ?? '')
    if (level > 0 && (!same || level > before.level)) {
      await update($, warned, () => ({ resetsAt: week.resetsAt ?? '', level }))
      $.ui.toast(`Weekly plan usage passed ${level}% (${week.percentUsed}%), ${until(week.resetsAt, now)}`, { timeoutMs: 8000 })
    }
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'usage-meter', description: 'Show the plan usage pane (5-hour and weekly windows)' })
    await $.tool.register({
      name: 'usage',
      description:
        "The account's plan usage right now: each rate-limit window (5-hour, weekly) with the percent used and when it " +
        'resets, and what this session has cost at API prices. Read it before starting or sizing heavy work such as a ' +
        'workflow with many agents.',
      inputSchema: { type: 'object', properties: {} },
      isDeferred: false,
    })
    const u = await $.session.usage()
    await record($, u.rateLimits, u.cost?.usd)
    $.clock.every(60_000, () => void update($, tick, n => (n ?? 0) + 1))
    void $.ui.open({ id: PANE, title: TITLE })
    return next(e)
  })

  on('session.measure', async ($, e, next) => {
    if (e.changed.includes('rateLimits') || e.changed.includes('cost')) await record($, e.rateLimits, e.cost?.usd)
    return next(e)
  })

  on('command.run', { command: 'usage-meter' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })
    return { text: summary(await read($, reading), await $.clock.now()) }
  })

  on('tool.call', { tool: 'mcp__usage-meter__usage' }, async $ => {
    const u = await $.session.usage() // fresh from the last API response, not only the last stored reading
    if (u.rateLimits.length) await record($, u.rateLimits, u.cost?.usd)
    const now = await $.clock.now()
    const r = u.rateLimits.length ? { at: now, windows: windowsOf(u.rateLimits), costUsd: u.cost?.usd } : await read($, reading)
    return { result: summary(r, now) }
  }).catch(async $ => ({
    result: `usage-meter could not read the usage now. Last stored reading:\n${summary(await read($, reading), await $.clock.now())}`,
  }))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    await read($, tick) // redraw each minute
    const r = await read($, reading)
    const now = await $.clock.now()
    const cols = Math.max(20, (e.props as { bodyColumns?: number }).bodyColumns ?? e.viewport?.columns ?? 40)
    const barWidth = Math.max(10, Math.min(40, cols - 12))
    if (!r || r.windows.length === 0)
      return (
        <Box flexDirection="column">
          <Text dimColor>No reading yet. The plan's windows arrive with the next API response.</Text>
        </Box>
      )
    return (
      <Box flexDirection="column">
        {r.windows.map(w => {
          const filled = Math.round((Math.min(100, Math.max(0, w.percentUsed)) / 100) * barWidth)
          const color = w.percentUsed >= 90 ? 'error' : w.percentUsed >= 75 ? 'warning' : 'success'
          return (
            <Box flexDirection="column" marginBottom={1}>
              <Text weight="bold">
                {label(w.kind)} <Text color={color}>{w.percentUsed}%</Text>
              </Text>
              <Text>
                <Text color={color}>{'█'.repeat(filled)}</Text>
                <Text dimColor>{'░'.repeat(barWidth - filled)}</Text>
              </Text>
              <Text dimColor>
                {until(w.resetsAt, now)}
                {w.resetsAt ? ` · ${at(w.resetsAt)}` : ''}
              </Text>
            </Box>
          )
        })}
        {r.costUsd !== undefined && <Text dimColor>This session: ${r.costUsd.toFixed(2)} at API prices</Text>}
        <Text dimColor>Read {Math.max(0, Math.round((now - r.at) / 60_000))} min ago</Text>
      </Box>
    )
  })
}
