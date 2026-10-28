import { describe, expect, it } from 'vitest'
import type { ChatStreamEvent } from '@/types/api'
import { pendingCard } from './pendingCard'
import { applyTraceEvent } from './trace'
import type { ChatTraceStep } from './types'

const steps = (...events: ChatStreamEvent[]): ChatTraceStep[] => events.reduce(applyTraceEvent, [] as ChatTraceStep[])

describe('pendingCard', () => {
  it('should expect the plan once the trip is built, while the model still thinks and writes', () => {
    // xAI sends the call to show the plan whole, at the very end: the built trip is the signal
    const built = steps({ type: 'tool_start', name: 'build_trip' }, { type: 'tool_end', name: 'build_trip' })

    expect(pendingCard(built)).toBe('plan')
  })

  it('should expect the cards once places are found, and nothing while another step runs', () => {
    const found = steps({ type: 'tool_start', name: 'search_destinations' }, { type: 'tool_end', name: 'search_destinations' })

    expect(pendingCard(found)).toBe('cards')
    expect(pendingCard([...found, ...steps({ type: 'tool_start', name: 'research' })])).toBeNull()
    expect(pendingCard(steps({ type: 'tool_preparing', name: 'show_trip' }))).toBe('plan')
    expect(pendingCard(steps({ type: 'tool_start', name: 'update_trip_brief' }, { type: 'tool_end', name: 'update_trip_brief' }))).toBeNull()
  })
})
