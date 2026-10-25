export interface ChatRequest {
  query: string
  chat_id?: string
  origin?: string
  answers?: BriefAnswers
}

export type TripKind = 'sea' | 'mountains' | 'city' | 'nature' | 'ski'
export type ClarifySlot = 'vibe' | 'when' | 'travelers' | 'budget'

/** What the user picked on the question cards; the server merges it into the trip brief. */
export interface BriefAnswers {
  kinds?: TripKind[]
  month?: number
  nights_min?: number
  nights_max?: number
  adults?: number
  children?: number
  children_ages?: number[]
  budget_level?: number
  budget_total_rub?: number
}

export interface ClarifyQuestion {
  slot: ClarifySlot
  title: string
  hint?: string | null
}

export interface ClarifyPrefill {
  kinds: TripKind[]
  month: number | null
  nights: [number, number] | null
  adults: number | null
  children: number | null
  children_ages: number[]
  budget_level: number | null
}

export interface ClarifyEvent {
  type: 'clarify'
  questions: ClarifyQuestion[]
  prefill: ClarifyPrefill
}

export interface DestinationClimate {
  month: string
  /** «в ноябре» */
  month_in: string
  day?: number
  night?: number
  sea?: number
  rain_days?: number
}

export interface DestinationCard {
  id: string
  name: string
  country: string
  country_code: string
  kinds: TripKind[]
  flight_hours?: number | null
  direct?: boolean | null
  train_hours?: number | null
  visa: string
  visa_easy: boolean
  price_level: number
  price: string
  kids: string
  kids_fit: 'good' | 'ok' | 'poor'
  climate: DestinationClimate | null
  highlights: string[]
  watch_out: string[]
  why: string
  tradeoff?: string | null
  image?: string | null
}

export interface DestinationsEvent {
  type: 'destinations'
  summary: string[]
  cards: DestinationCard[]
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
  | ClarifyEvent
  | DestinationsEvent
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
