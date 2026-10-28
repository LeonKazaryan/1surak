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
  /** The browser's other chats: the traveller's earlier trips, which the agent may offer, never apply. */
  history?: string[]
  /** Facts the traveller hid on «Что я о вас помню». */
  forget?: string[]
}

/** Something the traveller's earlier trips say about them, with the trip it comes from. */
export interface MemoryFact {
  /** «party», «budget», «wish:с видом на море»: sent back in `forget` to hide it. */
  key: string
  /** «Кто едет» */
  label: string
  /** «вдвоём + ребёнок 6 лет» */
  text: string
  /** «Хургада · ноябрь» */
  source: string
  chat_id: string
}

/** An idea on the start screen: a message to send, or an earlier trip to open. */
export interface Idea {
  label: string
  query?: string | null
  chat_id?: string | null
  /** What in memory it comes from: «бронь 1S-ABC234», «помню: вдвоём + ребёнок 6 лет». */
  why?: string | null
}

export interface MemoryResponse {
  facts: MemoryFact[]
  ideas: Idea[]
}

/** A quick reply from the traveller's earlier trips, once per trip: «Как в прошлый раз: с видом на море». */
export interface MemoryNudge {
  text: string
  source: string
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

/** What an earlier trip answered to a question, offered on its card as «Как в прошлый раз». */
interface Recalled {
  /** «вдвоём + ребёнок 6 лет» */
  text: string
  /** «Хургада · ноябрь» */
  source: string
}

export interface ClarifyRemembered {
  travelers?: Recalled & { adults: number; children: number; children_ages: number[] }
  budget?: Recalled & { budget_level?: number; budget_total?: number; budget_currency?: string }
  visa?: Recalled & { visa_free_only: boolean }
}

export interface ClarifyEvent {
  type: 'clarify'
  questions: ClarifyQuestion[]
  prefill: ClarifyPrefill
  currency?: Currency
  /** From the traveller's earlier trips, per question: one tap fills it, nothing is filled by itself. */
  remembered?: ClarifyRemembered
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

/** What a visa costs, found once on the web (an official page where there is one) and cached. */
export interface VisaFee {
  /** 0: the visa is free. */
  amount: number
  /** ISO 4217, as the source states it. */
  currency: string
  /** «консульский сбор за туристическую визу B1/B2» */
  covers: string
  /** The amount in roubles when the currency is one we convert; the UI shows it in the user's currency. */
  rub: number | null
  /** The site: «travel.state.gov». */
  source: string
  url: string
  /** ISO date it was found. */
  checked: string
}

/** The visa for the traveller's own passport (the departure country's), from the Passport Index. */
export interface VisaInfo {
  rule: 'none' | 'visa_free' | 'on_arrival' | 'eta' | 'evisa' | 'visa_required' | 'no_admission'
  /** «нужна виза», «без визы до 30 дней» */
  label: string
  /** «Для граждан Казахстана нужна виза в США, …» */
  text: string
  days: number | null
  /** «KZ-US»: passport and destination, to ask GET /api/visa/{pair} for the fee. */
  pair: string
  /** null: not found yet (or not anywhere); the chip asks when it opens. */
  fee?: VisaFee | null
  /** On a route: what the chip names, the country or the visa area («Шенген»). */
  name?: string
  /** The countries one visa of an area opens on this route: «Италия», «Испания», «Португалия». */
  countries?: string[]
  /** Countries outside the area on this route that let its visa in instead of their own, with the source. */
  also?: { name: string; days: number | null; source: string; url: string }[]
}

export interface DestinationCard {
  type?: 'place'
  id: string
  name: string
  country: string
  country_code: string
  lat?: number
  lon?: number
  kinds: TripKind[]
  flight_hours?: number | null
  direct?: boolean | null
  train_hours?: number | null
  visa: string
  visa_easy: boolean
  visa_info?: VisaInfo | null
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
  lat?: number
  lon?: number
  kinds: TripKind[]
  nights: number
  day: number | null
  sea: number | null
  visa: string
  visa_easy: boolean
  visa_info?: VisaInfo | null
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
  /** No fare cached for the leg's dates: the best ticket of the nearest dates, a guide to the price. */
  guide?: RouteFlight
  /** The day the plan has a flight without a ticket on, «2027-03-10». */
  date?: string
  /** The live search on Aviasales for that day. */
  search_link?: string | null
  /** The ticket costs clearly more than the route usually does that month: the usual fare. */
  usual_rub?: number
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
  /** One chip per visa to get: the Schengen countries of the route share one. */
  visas?: VisaInfo[]
  total_rub: number | null
  total_complete: boolean
  /** Part of the total is the best fare of the nearest dates, for flights with no fare on their day. */
  total_guided?: boolean
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
  /** No fare cached: the live search on Aviasales for the leg's day. */
  search_link?: string
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

/** The room a live offer sells, as the hotel names it; size, beds, view and amenities are said in Russian. */
export interface PlanRoom {
  name: string | null
  size_m2: number | null
  beds: string | null
  view: string | null
  amenities: string[]
  /** How many of the hotel's `photos` are this room's: they come first. */
  photos: number
}

/** A hotel with a live offer (LiteAPI): its photos, the room it sells, the refund deadline and whose price it is. */
export interface LiveOffer {
  photos?: string[]
  room?: PlanRoom | null
  /** What guests rate it for: «Расположение» 9.1. */
  scores?: { label: string; score: number }[]
  /** Free cancellation until this day. */
  cancel_until?: string | null
  /** «LiteAPI»: the price is the provider's for these dates; absent for an estimate. */
  price_source?: string | null
  /** The provider's test rates: the hotel and room are real, the price is for trying it out. */
  sandbox?: boolean
}

/** One hotel of search_hotels: real ones carry their photo and source; the price is for the whole stay. */
export interface HotelOption extends LiveOffer {
  id: string
  name: string
  stars: number
  stars_known: boolean
  area: string
  photo: Photo | null
  source_url: string | null
  /** A real hotel on Google Maps; null for a demo hotel. */
  maps_url?: string | null
  real: boolean
  meal_label: string
  night_rub: number
  total_rub: number
  price_estimate: boolean
  terms_known: boolean
  /** The hotel already in the plan. */
  current: boolean
  evidence?: HotelEvidence[]
  rating?: number | null
  reviews?: number | null
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
  country?: string
}

export interface DestinationsEvent {
  type: 'destinations'
  summary: string[]
  /** Children travel: only then the cards say how a place suits them. */
  with_kids?: boolean
  cards: DestinationsCard[]
  currency?: Currency
  /** The departure city, where the arcs of the map start. */
  origin?: { code: string; name: string; lat: number; lon: number } | null
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
  /** The place on Google Maps: its own listing, or a search for its name around its point. */
  maps_url: string | null
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
export interface PlanHotel extends LiveOffer {
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
  /** A real hotel on Google Maps; null for a demo hotel. */
  maps_url?: string | null
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
  /** The site of the city's airport taxi fare the price is scaled from; null: an estimate by the kilometre. */
  source?: string | null
}

export interface PlanStop {
  place_id: string
  name: string
  country: string
  country_code: string
  lat?: number
  lon?: number
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
  /** The part of `flights` priced by the nearest dates: those flights have no fare on their day yet. */
  flights_guide?: number
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

/** The trip field by field, for the chat's header: it fills in as the agent understands the request. */
export interface TripPassport {
  destination: {
    name: string
    country_code: string | null
    place_id: string | null
    photo: Photo | null
    lat: number | null
    lon: number | null
  } | null
  kinds: { kind: TripKind; label: string }[]
  month: number | null
  /** «Ноябрь · 11–14 ночей» */
  when: string | null
  /** «2 взрослых + 1 ребёнок (5 лет)» */
  travelers: string | null
  /** «Средний бюджет», «до 500 000 ₸» */
  budget: string | null
  origin: { code: string; name: string; from: string; lat: number; lon: number } | null
  multi_city: boolean
  /** «Несколько стран»: every route crosses several of them. */
  multi_country?: boolean
  visa_free_only: boolean
  by_land: boolean
  wishes: string[]
}

/** A number about the agent's work: «120 направлений из города». */
export interface ToolFact {
  value: number
  label: string
}

/** What a saved trip looks like now: its brief, where the tickets fly from, and whether they still hold. */
export interface TripStatus {
  summary: string[]
  passport?: TripPassport | null
  /** «из Астаны» */
  departure: string | null
  priced_at: string | null
  /** The tickets were found more than a day ago. */
  stale: boolean
  dates_passed: boolean
  nudge?: MemoryNudge | null
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
  /** The model began a call and is still writing its arguments: the screen says what is coming. */
  | { type: 'tool_preparing'; name: string; title?: string }
  | { type: 'tool_start'; name: string; title?: string; args?: Record<string, unknown> }
  | { type: 'tool_end'; name: string; output_preview?: string; facts?: ToolFact[] }
  | { type: 'brief'; passport: TripPassport }
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
