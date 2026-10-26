import type { Dispatch, SetStateAction } from 'react'
import type { BookingEvent, ChatMeta, ClarifyEvent, DestinationsEvent, FlightPlanEvent, TripPlanEvent } from '@/types/api'

/** One visible step of the agent's work: a tool call, a note, or an error. */
export interface ChatTraceStep {
  id: string
  kind: 'tool' | 'note' | 'error'
  name?: string
  title?: string
  args?: Record<string, unknown>
  detail?: string
  resultLine?: string
  status: 'running' | 'done'
}

/** What the agent shows under its message: questions, destinations, the trip plan, or a booking. */
export type ChatWidget = ClarifyEvent | DestinationsEvent | TripPlanEvent | BookingEvent | FlightPlanEvent

export interface WorkspaceChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  traceSteps?: ChatTraceStep[]
  widget?: ChatWidget
  /** While streaming: is the agent running tools or writing text. Drives the flight loader. */
  phase?: 'working' | 'writing'
  timestamp: Date
}

export interface ChatLayoutContext {
  chatMessages: WorkspaceChatMessage[]
  setMessages: Dispatch<SetStateAction<WorkspaceChatMessage[]>>
  activeChatId: string | null
  setActiveChatId: Dispatch<SetStateAction<string | null>>
  setRecentChats: Dispatch<SetStateAction<ChatMeta[]>>
}
