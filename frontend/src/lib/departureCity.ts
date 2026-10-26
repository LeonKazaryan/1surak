export interface DepartureCity {
  code: string
  name: string
  country?: string
  lat?: number
  lon?: number
}

const KEY = '1surak.departureCity'
/** Only until the city is detected or picked: every other city comes from Aviasales. */
export const FALLBACK_CITY: DepartureCity = { code: 'MOW', name: 'Москва', country: 'Россия', lat: 55.75, lon: 37.62 }

/** The saved city, or null when the user never picked one (then we detect it). */
export function savedDepartureCity(): DepartureCity | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw?.startsWith('{')) return null
    const city = JSON.parse(raw) as DepartureCity
    return /^[A-Z]{3}$/.test(city.code) && city.name ? city : null
  } catch {
    return null
  }
}

export function getDepartureCity(): DepartureCity {
  return savedDepartureCity() ?? unsaved ?? FALLBACK_CITY
}

const CHANGED = '1surak:departure-city'
let unsaved: DepartureCity | null = null // when storage is blocked, the choice still lasts until a reload

export function saveDepartureCity(city: DepartureCity): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(city))
    unsaved = null
  } catch {
    // Storage full or blocked (private mode): the choice lasts until the page reloads.
    unsaved = city
  }
  window.dispatchEvent(new CustomEvent<DepartureCity>(CHANGED, { detail: city }))
}

/** Every picker on the page follows a change made anywhere: another picker, or the agent. */
export function onDepartureCityChange(listener: (city: DepartureCity) => void): () => void {
  const handle = (e: Event) => listener((e as CustomEvent<DepartureCity>).detail)
  window.addEventListener(CHANGED, handle)
  return () => window.removeEventListener(CHANGED, handle)
}

/** False while the city is the Moscow fallback: nobody detected, picked or confirmed it. */
export function departureCityKnown(): boolean {
  return savedDepartureCity() !== null || unsaved !== null
}

// Aviasales (Travelpayouts) open endpoints: no key, CORS allowed, so the browser calls them directly
// and the location comes from the user's own IP, not the server's.
const AUTOCOMPLETE = 'https://autocomplete.travelpayouts.com/places2'
const WHEREAMI = 'https://www.travelpayouts.com/whereami'

interface Place {
  code: string
  name: string
  country_name?: string
  coordinates?: { lat: number; lon: number }
}

export async function searchCities(term: string, signal?: AbortSignal): Promise<DepartureCity[]> {
  const url = `${AUTOCOMPLETE}?term=${encodeURIComponent(term)}&locale=ru&types[]=city`
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`${res.status}`)
  const places = (await res.json()) as Place[]
  return places.map((p) => ({
    code: p.code,
    name: p.name,
    country: p.country_name,
    lat: p.coordinates?.lat,
    lon: p.coordinates?.lon,
  }))
}

/** The nearest city with an airport, by the user's IP. */
export async function detectCity(signal?: AbortSignal): Promise<DepartureCity | null> {
  const res = await fetch(`${WHEREAMI}?locale=ru`, { signal })
  if (!res.ok) return null
  const data = (await res.json()) as { iata?: string; name?: string; country_name?: string; coordinates?: string }
  if (!data.iata || !data.name) return null
  const [lon, lat] = (data.coordinates ?? '').split(':').map(Number)
  return { code: data.iata, name: data.name, country: data.country_name, lat, lon }
}

/** Cities with an airport around a point, from our Travelpayouts dictionary. */
export async function nearbyCities(lat: number, lon: number, signal?: AbortSignal): Promise<DepartureCity[]> {
  const res = await fetch(`/api/places/nearby?lat=${lat}&lon=${lon}&limit=9`, { signal })
  if (!res.ok) return []
  return ((await res.json()) as { items: DepartureCity[] }).items
}
