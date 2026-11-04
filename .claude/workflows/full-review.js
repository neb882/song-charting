export const meta = {
  name: 'full-review',
  description: 'Review an integrated songcharter change through several lenses, test the tests, and have a skeptic try to refute each finding',
  whenToUse: 'Once over an integrated release (docs/PIPELINE.md, the release gate), or another big or risky integration. Pass args: {base, head, worktree, brief?, lenses?, perLens?}.',
  phases: [
    { title: 'Review', detail: 'one reviewer per lens over the diff base...head' },
    { title: 'Verify', detail: 'one skeptic per finding' },
  ],
}

// args:
//   base, head  commits or branches; the diff is base...head
//   worktree    a checkout of head for the agents to read (they never edit it)
//   brief       optional: what the release is for and which files or orders it covers
//   lenses      optional: [{key, text}] to replace the default lenses
//   perLens     optional: how many findings per lens to verify (default 5)
// It returns the confirmed findings. Fixing them goes to the orders' builders (docs/PIPELINE.md).

const A = args || {}
if (!A.base || !A.head || !A.worktree) throw new Error('full-review needs args {base, head, worktree}')
const PER_LENS = A.perLens || 5

const COMMON = `You review songcharter, a public repository. Read CLAUDE.md and docs/PIPELINE.md in ${A.worktree} first.

The change: \`git -C ${A.worktree} diff ${A.base}...${A.head}\`.
${A.brief ? `What it is: ${A.brief}` : ''}

Rules:
- You can't edit the repository. Work on copies under /dev/shm/fr_<your lens>/, and delete that folder when done.
- Never run two heavy jobs at once: the machine is shared.
- Report only real defects, each reproduced with a command or script and its output. Skip style and taste: an empty
  list is a good answer.
- Never print or save song lyrics or personal details.`

const DEFAULT_LENSES = [
  { key: 'correct', text: 'LENS: correctness for the friend\'s real use: a song in, a chart in Clone Hero out. Look for wrong results, crashes, broken contracts (exit codes, determinism, the gate), and any silent CPU fallback.' },
  { key: 'tests', text: 'LENS: test the tests. Break each new or changed check, gate or guard 3–5 ways in a copy, and report every break the tests miss that would ship a real defect.' },
  { key: 'install', text: 'LENS: the install and the environment. What the friend\'s machine (WSL2, Ubuntu 26.04 or 22.04, a GPU lane, 16 GB) gets that CI\'s does not; partial states, resumes, and anything deleted or overwritten that is not ours.' },
  { key: 'docs', text: 'LENS: docs and evidence. Claims in DESIGN.md, the work orders, the README and the guide that the code or the reports in docs/reports/ contradict, and numbers that do not match their source.' },
]
const LENSES = A.lenses || DEFAULT_LENSES

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          severity: { type: 'string', enum: ['major', 'minor'] },
          title: { type: 'string' },
          detail: { type: 'string' },
          repro: { type: 'string' },
        },
        required: ['id', 'severity', 'title', 'detail', 'repro'],
      },
    },
  },
  required: ['findings'],
}
const VERDICT = {
  type: 'object',
  properties: {
    real: { type: 'boolean' },
    severity: { type: 'string', enum: ['major', 'minor', 'none'] },
    why: { type: 'string' },
  },
  required: ['real', 'severity', 'why'],
}

phase('Review')
const reviewed = await pipeline(
  LENSES,
  l => agent(`${COMMON}\n\n${l.text}\n\nReturn at most 6 findings, most severe first, with ids prefixed "${l.key}-".`, { label: `review:${l.key}`, phase: 'Review', schema: FINDINGS }),
  (r, l) => {
    const all = r && r.findings ? r.findings : []
    if (all.length > PER_LENS) log(`review:${l.key} returned ${all.length} findings; verifying the first ${PER_LENS}`)
    return parallel(all.slice(0, PER_LENS).map(f => () => agent(`${COMMON}

Your task: try to refute this finding. Reproduce it yourself (work under /dev/shm/frv_${f.id}/, and delete it when done). Judge it not real if you cannot reproduce it, if it is intended and documented, or if no real run could reach it. When unsure, say not real. If it is real, say in a few lines the fix you would make.

FINDING ${f.id} (${f.severity}): ${f.title}
${f.detail}
Repro: ${f.repro}`, { label: `verify:${f.id}`, phase: 'Verify', schema: VERDICT }).then(v => ({ lens: l.key, ...f, verdict: v }))))
  },
)
const all = reviewed.flat().filter(Boolean)
const confirmed = all.filter(f => f.verdict && f.verdict.real)
log(`${all.length} findings verified, ${confirmed.length} confirmed (${confirmed.filter(f => f.verdict.severity === 'major').length} major)`)
return {
  confirmed: confirmed.map(f => ({ id: f.id, lens: f.lens, severity: f.verdict.severity, title: f.title, detail: f.detail, fix: f.verdict.why })),
  refuted: all.filter(f => !(f.verdict && f.verdict.real)).map(f => ({ id: f.id, title: f.title, why: f.verdict ? f.verdict.why : 'no verdict' })),
}
