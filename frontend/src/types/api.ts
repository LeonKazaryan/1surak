export interface ChatRequest {
  query: string
  chat_id?: string
  origin?: string
  /** IATA code of the departure city: the agent searches real tickets from it. */
  origin_code?: string
  answers?: BriefAnswers
  /** Ask again in place of the last turn, when that turn failed. */
  retry?: boolean
  /** False when the city could not be detected and is the Moscow fallback: the agent asks for it. */
  origin_known?: boolean
}

export type TripKind = 'sea' | 'mountains' | 'city' | 'nature' | 'ski'
export type ClarifySlot = 'origin' | 'vibe' | 'when' | 'travelers' | 'route' | 'budget'

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
  /** In budget_currency, the user's own unless they named another. */
  budget_total?: number
  budget_currency?: string
  multi_city?: boolean
  /** IATA code of the departure city, when the user picked or confirmed it on the cards. */
  origin?: string
}

/** The user's currency, picked by the server from the departure city. Prices stay in roubles until shown. */
export interface Currency {
  code: string
  sign: string
  /** Repeated for a price level (₸₸₸). */
  glyph: string
  per_rub: number
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
  /** The city the tickets fly from right now. */
  origin?: { code: string; name: string } | null
  /** The sum the user named, in their own currency. */
  budget_total?: number | null
}

export interface ClarifyEvent {
  type: 'clarify'
  questions: ClarifyQuestion[]
  prefill: ClarifyPrefill
  currency?: Currency
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
  /** Formatted in the user's currency by the server. */
  price?: string
  from_airport?: string
  to_airport?: string
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
  photo?: Photo | null
  price_change?: PriceChange
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
  photo?: Photo | null
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
  price_change?: PriceChange
}

export type DestinationsCard = DestinationCard | RouteCard

/** Two tickets through a hub that cost less than the leg's own, with the wait between them. */
export interface FlightConnection {
  via: string
  price_rub: number
  hours: number
  layover_hours: number
  separate_tickets: boolean
  saves_rub: number | null
  tickets: FlightTicket[]
}

/** One leg of a trip through the cities the user named: a ticket to buy, a train, or no way yet. */
export interface FlightPlanLeg {
  from: string
  to: string
  mode: 'flight' | 'train' | 'none'
  km: number | null
  hours?: number
  ticket?: RouteFlight
  estimate?: string
  via?: FlightConnection
}

export interface FlightPlan {
  id: string
  name: string
  best: boolean
  legs: FlightPlanLeg[]
  total_rub: number | null
  total_complete: boolean
  total_with_connections_rub: number | null
  /** Every flight leaves after the one before: the tickets make one trip. */
  dates_chained: boolean
  travel_hours: number | null
}

/** plan_route's answer: the user's cities in the best order(s), every leg priced, with links to buy. */
export interface FlightPlanEvent {
  type: 'flight_plan'
  from: string
  plans: FlightPlan[]
  currency?: Currency
}

/** The agent now searches from another city (the user named it): the picker follows. */
export interface OriginEvent {
  type: 'origin'
  code: string
  name: string
}

export interface DestinationsEvent {
  type: 'destinations'
  summary: string[]
  cards: DestinationsCard[]
  currency?: Currency
}

/** A real photo from Wikimedia Commons: shown with its author and licence. */
export interface Photo {
  url: string
  width: number
  height: number
  author: string
  license: string
  file_url: string
}

/** A sight or a food place from Wikivoyage. */
export interface PlanSpot {
  id: string
  type: string
  name: string
  alt: string | null
  summary: string
  hours: string | null
  price: string | null
  photo: Photo | null
  lat: number | null
  lon: number | null
  source_url: string | null
}

export type PlanItemKind = 'sight' | 'trip' | 'food' | 'beach' | 'walk' | 'free' | 'flight' | 'transfer' | 'hotel' | 'move'

export interface PlanItem {
  kind: PlanItemKind
  title: string
  /** Local time «14:15»; null while the flights are not on the plan's dates yet. */
  time: string | null
  note: string | null
  spot: PlanSpot | null
}

export interface PlanDay {
  date: string
  title: string
  place_id: string
  items: PlanItem[]
}

/** A demo hotel, shaped like an Ostrovok offer: prices in roubles for all rooms of the party. */
export interface PlanHotel {
  id: string
  name: string
  stars: number
  rating: number
  reviews: number
  area: string
  beach_m: number | null
  meal: string
  meal_label: string
  /** Free cancellation until this many days before arrival; null: no refund. */
  free_cancel_days: number | null
  pay_at_hotel: boolean
  rooms: number
  nights: number
  night_rub: number
  total_rub: number
  check_in: string
  check_out: string
  reasons: string[]
  misses: string[]
  demo: boolean
}

export interface PlanTransfer {
  mode: 'car' | 'boat'
  km: number
  minutes: number
  price_rub: number
}

export interface PlanStop {
  place_id: string
  name: string
  country: string
  country_code: string
  kinds: TripKind[]
  check_in: string
  check_out: string
  nights: number
  photo: Photo | null
  source_url: string | null
  hotel: PlanHotel
  alternatives: PlanHotel[]
  excluded: { name: string; stars: number; reason: string }[]
  transfer_in: PlanTransfer | null
  transfer_out: PlanTransfer | null
  food_intro: string | null
  dishes: { name: string; note: string }[]
}

export interface PlanLeg extends RouteLeg {
  /** Local times «2026-11-06T09:40»; null when the tickets do not follow the plan's dates. */
  departs: string | null
  arrives: string | null
  /** A ground hop per person, an estimate. */
  ground_rub: number | null
}

/** Something the user can add to fix a timing problem, like an early check-in. */
export interface PlanFix {
  /** «early_check_in:antalya-h3»: one per hotel, so each stop of a route has its own. */
  id: string
  type: 'early_check_in' | 'late_check_out'
  label: string
  price_rub: number
}

export interface PlanCheck {
  level: 'ok' | 'info' | 'warn'
  title: string
  text: string
  fix: PlanFix | null
  /** What was checked: the times where the pieces meet, the tickets, a hop by land, the budget. */
  kind: 'timing' | 'tickets' | 'move' | 'budget'
}

/** All in roubles, for the whole party. */
export interface PlanCosts {
  flights: number
  hotels: number
  transfers: number
  ground: number
  total: number
  per_person: number
  guests: number
  flights_complete: boolean
  budget: number | null
  over_by: number | null
}

/** The whole trip the agent assembled: tickets, hotels, rides, checks, days and the bill. */
export interface TripPlanEvent {
  type: 'trip_plan'
  id: string
  name: string
  dates: { from: string; to: string; nights: number }
  /** The tickets follow the plan's dates; otherwise dates are ours and the flight times unknown. */
  dates_fixed: boolean
  party: { adults: number; children_ages: number[] }
  stops: PlanStop[]
  legs: PlanLeg[]
  checks: PlanCheck[]
  days: PlanDay[]
  costs: PlanCosts
  unmet: string[]
  changes: string[]
  summary: string[]
  currency?: Currency
}

/** A simulated purchase of the latest plan. */
export interface BookingEvent {
  type: 'booking'
  number: string
  plan_message_id: string
  name: string
  dates: { from: string; to: string; nights: number }
  holder: string
  extras: PlanFix[]
  total_rub: number
  currency?: Currency | null
}

export interface BookingRequest {
  extras: PlanFix['id'][]
  holder: string
}

/** What a saved trip looks like now: its brief, where the tickets fly from, and whether they still hold. */
export interface TripStatus {
  summary: string[]
  /** «из Астаны» */
  departure: string | null
  priced_at: string | null
  /** The tickets were found more than a day ago. */
  stale: boolean
  dates_passed: boolean
}

/** How a card's price moved since the last check: positive got dearer. */
export interface PriceChange {
  rub: number
  since: string
}

export interface ChatStreamDone extends Partial<TripStatus> {
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
  | TripPlanEvent
  | BookingEvent
  | FlightPlanEvent
  | OriginEvent
  | ChatStreamDone

export interface ChatMeta extends Partial<TripStatus> {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface RefreshResponse {
  message: ChatMessageOut
  chat: ChatMeta
}

export interface ChatMessageOut {
  id: string
  chat_id: string
  role: 'user' | 'assistant'
  content: string
  trace: unknown[]
  created_at: string
}
