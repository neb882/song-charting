/** One rate-limit window as the engine last reported it. */
export type Window = { kind: string; percentUsed: number; resetsAt?: string }

/** The last measurement: when it was taken, the windows and the session's cost. */
export type Reading = { at: number; windows: Window[]; costUsd?: number }

declare module 'claude-code' {
  interface PluginState {
    'usage-meter': {
      reading: Shaped<Reading | null>
      /** The highest weekly threshold already toasted, per reset time (so a new week starts over). */
      warned: Shaped<{ resetsAt: string; level: number } | null>
      /** Bumped once a minute so the pane's "resets in" stays right. */
      tick: number
    }
  }
}
