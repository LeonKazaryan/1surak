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
  /** The currency picked on the start screen; omitted to follow the departure city. */
  currency?: string
}

export type TripKind = 'sea' | 'mountains' | 'city' | 'nature' | 'ski'
export type ClarifySlot = 'origin' | 'vibe' | 'when' | 'travelers' | 'route' | 'budget' | 'visa'

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
  /** True: only places without a visa; false: every place, the ones needing a visa marked. */
  visa_free_only?: boolean
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
  visa_free_only?: boolean | null
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
  /** The team's estimates; null for a city from the route map, which nobody has checked. */
  price_level: number | null
  price: string | null
  kids: string | null
  kids_fit: 'good' | 'ok' | 'poor' | null
  climate: DestinationClimate | null
  flight?: RouteFlight | null
  highlights: string[]
  watch_out: string[]
  why: string
  tradeoff?: string | null
  photo?: Photo | null
  price_change?: PriceChange
  /** False for a city from the route map: its facts are fetched, not checked by the team. */
  verified?: boolean
  /** No cached ticket: the live search on Aviasales for this route. */
  search_link?: string | null
  /** No cached ticket: two tickets through the country's main airport (estimate when the days do not connect). */
  flight_via?: { via: string; via_in?: string; price_rub: number; estimate: boolean; tickets: FlightTicket[] } | null
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

/** A real train (Tutu timetable) or bus (FlixBus ride on the day) for a hop by land. */
export interface GroundRide {
  mode: 'train' | 'bus'
  /** «Туту.ру, расписание поездов» */
  source: string
  /** «Афросиаб 768Ф», «FlixBus» */
  name: string
  /** «16:49» from a timetable, or an ISO date-time for a ride on that day. */
  departs?: string
  arrives?: string
  hours: number
  price_rub?: number
  /** The class the price is for: «плацкарт», «сидячий». */
  fare?: string
  link: string
  dated?: boolean
  /** How many trains or buses run between the two. */
  options?: number
  /** Picked to fit the flight next to it: the hours at the station besides the transfer itself. */
  wait_hours?: number
  /** The line the source's terms require next to its data (Yandex.Rasp). */
  credit?: { text: string; link: string }
}

/** The direct flight a smarter way replaced, to show what it saves. */
export interface LegDetour {
  price_rub: number
  transfers: number
  hours: number
  airline: string
}

/** One leg of a route: a real ticket when it flies, a real train or bus (or an estimate) by land, or a smarter
 * way made of parts: train to Tashkent, then a direct flight home. */
export interface RouteLeg {
  from: string
  to: string
  mode: 'flight' | 'ground'
  km: number
  hours: number
  ticket?: RouteFlight
  ground?: GroundRide
  estimate?: string
  /** A hop by land without a train or bus found: a fare by distance. */
  estimate_rub?: number
  /** Index of the route's city the leg leaves or reaches; null for home. */
  from_stop?: number | null
  to_stop?: number | null
  parts?: RouteLeg[]
  /** The city a smart way changes in. */
  via?: string
  /** The parts together, per person; null while one of them has no fare. */
  price_rub?: number | null
  instead?: LegDetour
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
  kids: string | null
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

/** One wish of the guest checked against a hotel: what a real source says, word for word. */
export interface HotelEvidence {
  wish: string
  verdict: 'yes' | 'no' | 'unknown'
  quote: string | null
  /** The condition, if any: «собаки до 5 кг, за доплату». */
  note: string | null
  /** «сайт отеля», a review site's domain, «OpenStreetMap». */
  source: string | null
  source_url: string | null
}

/** One hotel of search_hotels: real ones carry their photo and source; the price is for the whole stay. */
export interface HotelOption {
  id: string
  name: string
  stars: number
  stars_known: boolean
  area: string
  photo: Photo | null
  source_url: string | null
  real: boolean
  meal_label: string
  night_rub: number
  total_rub: number
  price_estimate: boolean
  terms_known: boolean
  /** The hotel already in the plan. */
  current: boolean
  evidence?: HotelEvidence[]
}

export interface HotelOptionsEvent {
  type: 'hotel_options'
  place: string
  check_in: string
  nights: number
  guests: number
  hotels: HotelOption[]
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
  /** Children travel: only then the cards say how a place suits them. */
  with_kids?: boolean
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
  /** null for a real hotel: we never invent its guest rating. */
  rating: number | null
  reviews: number | null
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
  /** A real hotel (name, place, stars, photo); its price is an estimate until booking. */
  real?: boolean
  stars_known?: boolean
  photo?: Photo | null
  source_url?: string | null
  price_estimate?: boolean
  /** False: meals, refunds and payment are confirmed at booking, so the card claims none of them. */
  terms_known?: boolean
  evidence?: HotelEvidence[]
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
  /** What the same trip may come to: tickets are cached real prices, hotels and rides are estimates. */
  low?: number
  high?: number
  hotels_estimate?: boolean
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
  | HotelOptionsEvent
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
