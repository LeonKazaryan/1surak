import type { ChatTraceStep } from './types'

/** Which card the turn is about to show: the plan once the trip is built, the cards once places are found,
 * until it is on screen (the model still thinks and writes its reply meanwhile, often for half a minute).
 * Null while another step runs: its own loader says what it does. */
export function pendingCard(steps: ChatTraceStep[]): 'plan' | 'cards' | null {
  const running = steps.findLast((s) => s.status === 'running')
  if (running) return running.name === 'show_trip' ? 'plan' : running.name === 'show_destinations' ? 'cards' : null
  const done = new Set(steps.filter((s) => s.kind === 'tool').map((s) => s.name))
  if (done.has('build_trip')) return 'plan'
  if (done.has('search_destinations') || done.has('search_routes')) return 'cards'
  return null
}
