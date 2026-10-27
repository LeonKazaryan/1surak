import type { ChatStreamEvent } from '@/types/api'
import type { ChatTraceStep, WorkspaceChatMessage } from './types'

const RESULT_MAX_CHARS = 220

function summarizeResult(preview: string | undefined): string {
  const text = (preview ?? '').trim()
  if (!text) return 'Готово.'
  return text.length <= RESULT_MAX_CHARS ? text : `${text.slice(0, RESULT_MAX_CHARS - 1)}…`
}

function nextId(steps: ChatTraceStep[]): string {
  return `s-${steps.length}`
}

export function applyTraceEvent(steps: ChatTraceStep[], event: ChatStreamEvent): ChatTraceStep[] {
  switch (event.type) {
    case 'tool_start':
      return [
        ...steps,
        {
          id: nextId(steps),
          kind: 'tool',
          name: event.name,
          title: event.title ?? event.name,
          args: event.args,
          status: 'running',
        },
      ]
    case 'tool_end': {
      const resultLine = summarizeResult(event.output_preview)
      const index = steps.findLastIndex(
        (s) => s.kind === 'tool' && s.name === event.name && s.status === 'running',
      )
      const facts = event.facts?.length ? event.facts : undefined
      if (index === -1) {
        return [
          ...steps,
          { id: nextId(steps), kind: 'tool', name: event.name, title: event.name, status: 'done', resultLine, facts },
        ]
      }
      return steps.map((s, i) => (i === index ? { ...s, status: 'done', resultLine, facts } : s))
    }
    case 'assistant_note':
      return [...steps, { id: nextId(steps), kind: 'note', detail: event.text, status: 'done' }]
    case 'error':
      return [...steps, { id: nextId(steps), kind: 'error', detail: event.message, status: 'done' }]
    default:
      return steps
  }
}

function isTraceEvent(value: unknown): value is ChatStreamEvent {
  return typeof value === 'object' && value !== null && typeof (value as { type?: unknown }).type === 'string'
}

/** Rebuilds the trace of a saved assistant message from its persisted stream events. */
export function rehydrateTrace(events: unknown[]): ChatTraceStep[] {
  return events.filter(isTraceEvent).reduce(applyTraceEvent, [] as ChatTraceStep[])
}

/** A reply the agent could not finish: the server saved its error as the reply. */
export function isFailed(message: WorkspaceChatMessage): boolean {
  return message.role === 'assistant' && Boolean(message.traceSteps?.some((s) => s.kind === 'error'))
}
