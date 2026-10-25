export interface ChatRequest {
  query: string
  chat_id?: string
  origin?: string
  /** IATA code of the departure city: the agent searches real tickets from it. */
  origin_code?: string
  answers?: BriefAnswers
}

export type TripKind = 'sea' | 'mountains' | 'city' | 'nature' | 'ski'
export type ClarifySlot = 'vibe' | 'when' | 'travelers' | 'route' | 'budget'

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
  multi_city?: boolean
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
  multi_city: boolean | null
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

/** A real Aviasales ticket: the cheapest one way, one passenger, found in the last days. */
export interface FlightTicket {
  price_rub: number
  airline: string
  airline_name: string
  logo: string
  flight_number: string
  transfers: number
  hours: number
  departure: string
  link: string
}

export interface RouteFlight extends FlightTicket {
  direct_available: boolean
  direct_option?: FlightTicket
}

export interface DestinationCard {
  type?: 'place'
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
  flight?: RouteFlight | null
  highlights: string[]
  watch_out: string[]
  why: string
  tradeoff?: string | null
  image?: string | null
}

export interface RouteStop {
  id: string
  name: string
  country: string
  country_code: string
  kinds: TripKind[]
  nights: number
  day: number | null
  sea: number | null
  visa: string
  visa_easy: boolean
  highlights: string[]
}

/** One leg of a route: a real ticket when it flies, an estimate by distance when it goes by land. */
export interface RouteLeg {
  from: string
  to: string
  mode: 'flight' | 'ground'
  km: number
  hours: number
  ticket?: RouteFlight
  estimate?: string
}

export interface RouteInterest {
  kind: TripKind
  label: string
  covered: boolean
  wanted: boolean
}

/** A multi-city route: drawn as a wide card across two cells of the grid. */
export interface RouteCard {
  type: 'route'
  id: string
  name: string
  month: string | null
  month_in: string | null
  stops: RouteStop[]
  legs: RouteLeg[]
  total_rub: number | null
  total_complete: boolean
  /** Every flight leaves after the nights before it: the tickets make one trip, not separate cheapest ones. */
  dates_chained: boolean
  match: number
  interests: RouteInterest[]
  kids: string
  why: string
  tradeoff?: string | null
}

export type DestinationsCard = DestinationCard | RouteCard

export interface DestinationsEvent {
  type: 'destinations'
  summary: string[]
  cards: DestinationsCard[]
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
