import { describe, expect, it } from 'vitest'
import { applyTraceEvent, rehydrateTrace } from './trace'
import type { ChatStreamEvent } from '../types/api'
import type { ChatTraceStep } from './types'

function applyAll(events: ChatStreamEvent[]): ChatTraceStep[] {
  return events.reduce(applyTraceEvent, [] as ChatTraceStep[])
}

describe('applyTraceEvent', () => {
  it('should add a running step on tool_start using the backend title', () => {
    const steps = applyTraceEvent([], {
      type: 'tool_start',
      name: 'search_hotels',
      title: 'Ищу отели',
      args: { city: 'Казань' },
    })

    expect(steps).toEqual([
      {
        id: 's-0',
        kind: 'tool',
        name: 'search_hotels',
        title: 'Ищу отели',
        args: { city: 'Казань' },
        status: 'running',
      },
    ])
  })

  it('should fall back to the tool name when no title is sent', () => {
    const [step] = applyTraceEvent([], { type: 'tool_start', name: 'search_hotels' })

    expect(step.title).toBe('search_hotels')
  })

  it('should mark the latest running step with the same name as done on tool_end', () => {
    const started = applyAll([
      { type: 'tool_start', name: 'a' },
      { type: 'tool_start', name: 'b' },
    ])

    const steps = applyTraceEvent(started, { type: 'tool_end', name: 'a', output_preview: 'Найдено 3 отеля' })

    expect(steps.map((s) => s.status)).toEqual(['done', 'running'])
    expect(steps[0].resultLine).toBe('Найдено 3 отеля')
  })

  it('should not mutate the previous steps', () => {
    const started = applyTraceEvent([], { type: 'tool_start', name: 'a' })

    applyTraceEvent(started, { type: 'tool_end', name: 'a' })

    expect(started[0].status).toBe('running')
  })

  it('should add a done step when tool_end has no matching start', () => {
    const steps = applyTraceEvent([], { type: 'tool_end', name: 'a', output_preview: '' })

    expect(steps).toEqual([
      expect.objectContaining({ kind: 'tool', name: 'a', status: 'done', resultLine: 'Готово.' }),
    ])
  })

  it('should truncate a long tool result', () => {
    const started = applyTraceEvent([], { type: 'tool_start', name: 'a' })

    const [step] = applyTraceEvent(started, { type: 'tool_end', name: 'a', output_preview: 'x'.repeat(500) })

    expect(step.resultLine?.length).toBeLessThanOrEqual(220)
    expect(step.resultLine?.endsWith('…')).toBe(true)
  })

  it('should add notes for assistant_note and error events', () => {
    const steps = applyAll([
      { type: 'assistant_note', text: 'Уточняю даты' },
      { type: 'error', message: 'Не получилось' },
    ])

    expect(steps.map((s) => [s.kind, s.detail])).toEqual([
      ['note', 'Уточняю даты'],
      ['error', 'Не получилось'],
    ])
  })

  it('should ignore token and done events', () => {
    const steps: ChatTraceStep[] = []

    expect(applyTraceEvent(steps, { type: 'assistant_token', text: 'a' })).toBe(steps)
  })
})

describe('rehydrateTrace', () => {
  it('should rebuild steps from persisted events and skip junk', () => {
    const steps = rehydrateTrace([
      { type: 'tool_start', name: 'a', title: 'Шаг А' },
      null,
      'junk',
      { type: 'tool_end', name: 'a', output_preview: 'ok' },
    ])

    expect(steps).toEqual([expect.objectContaining({ title: 'Шаг А', status: 'done', resultLine: 'ok' })])
  })
})
