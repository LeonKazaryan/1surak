import type { Dispatch, SetStateAction } from 'react'
import type { ChatMeta, ClarifyEvent, DestinationsEvent } from '@/types/api'

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

/** Cards the agent shows under its message: questions to answer or destinations to pick from. */
export type ChatWidget = ClarifyEvent | DestinationsEvent

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
  planPanelOpen: boolean
  setPlanPanelOpen: Dispatch<SetStateAction<boolean>>
  activeChatId: string | null
  setActiveChatId: Dispatch<SetStateAction<string | null>>
  setRecentChats: Dispatch<SetStateAction<ChatMeta[]>>
}
