# usage-meter (a Claude Code mod for the orchestrating session)

The plan's 5-hour and weekly usage in a pane and the status line, toasts as the weekly window passes 50, 75 and
90 %, and a tool, `mcp__usage-meter__usage`, that the session reads before each wave and before sizing heavy work
(docs/PIPELINE.md: the owner's limit pauses new work at 70 % of the weekly usage). It reads only the session's own
rate-limit windows; nothing leaves the session.

A mod is not loaded from the repository. To install it in a new session:

1. Load the plugin-authoring skill (it starts the engine's watch and names the session's mods folder,
   `<dev-mods>/<session id>/`).
2. Copy this folder there as `usage-meter/` (the six files: `.claude-plugin/plugin.json`, `hooks/hooks.json`,
   `hooks/register.tsx`, `types/index.d.ts`, `tsconfig.json`, `tests/usage.test.tsx`).
3. Check it: `claude plugin validate <mod folder>`, `claude plugin test <mod folder>` (4 tests).
4. The owner answers the engine's one question ("Turn them on"); the mod loads when the turn ends. Call the tool
   once to confirm it answers (it is empty until the session's first API response).
