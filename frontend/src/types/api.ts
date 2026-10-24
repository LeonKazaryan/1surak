export interface ChatRequest {
  query: string
  chat_id?: string
  origin?: string
}

export interface ChatStreamDone {
  type: 'done'
  answer: string
  chat_id: string
  title: string | null
}

/** One NDJSON line from POST /api/chat/stream */
export type ChatStreamEvent =
  | { type: 'assistant_token'; text: string }
  | { type: 'assistant_note'; text: string }
  | { type: 'tool_start'; name: string; title?: string; args?: Record<string, unknown> }
  | { type: 'tool_end'; name: string; output_preview?: string }
  | { type: 'error'; message: string }
  | ChatStreamDone

export interface ChatMeta {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessageOut {
  id: string
  chat_id: string
  role: 'user' | 'assistant'
  content: string
  trace: unknown[]
  created_at: string
}
