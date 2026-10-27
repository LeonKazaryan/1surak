import type { Dispatch, SetStateAction } from 'react'
import type {
  BookingEvent,
  BriefAnswers,
  ChatMeta,
  ClarifyEvent,
  DestinationsEvent,
  FlightPlanEvent,
  HotelOptionsEvent,
  ToolFact,
  TripPlanEvent,
} from '@/types/api'

/** One visible step of the agent's work: a tool call, a note, or an error. */
export interface ChatTraceStep {
  id: string
  kind: 'tool' | 'note' | 'error'
  name?: string
  title?: string
  args?: Record<string, unknown>
  detail?: string
  resultLine?: string
  /** A few numbers about the work: «120 направлений → 5 подходят». */
  facts?: ToolFact[]
  status: 'running' | 'done'
}

/** What the agent shows under its message: questions, destinations, the trip plan, or a booking. */
export type ChatWidget = ClarifyEvent | DestinationsEvent | TripPlanEvent | BookingEvent | FlightPlanEvent | HotelOptionsEvent

export interface WorkspaceChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  traceSteps?: ChatTraceStep[]
  widget?: ChatWidget
  /** While streaming: is the agent running tools or writing text. Drives the flight loader. */
  phase?: 'working' | 'writing'
  /** A user message sent from the question cards: drawn as a receipt of the answers. */
  answers?: BriefAnswers
  timestamp: Date
}

export interface ChatLayoutContext {
  chatMessages: WorkspaceChatMessage[]
  setMessages: Dispatch<SetStateAction<WorkspaceChatMessage[]>>
  activeChatId: string | null
  setActiveChatId: Dispatch<SetStateAction<string | null>>
  setRecentChats: Dispatch<SetStateAction<ChatMeta[]>>
}
