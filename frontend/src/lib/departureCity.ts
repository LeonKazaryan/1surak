export interface DepartureCity {
  code: string
  name: string
  short?: string
  country?: string
  lat?: number
  lon?: number
}

/** Shown before the user types anything, nearest first. */
export const DEPARTURE_CITIES: DepartureCity[] = [
  { code: 'MOW', name: 'Москва', country: 'Россия', lat: 55.75, lon: 37.62 },
  { code: 'LED', name: 'Санкт-Петербург', short: 'Петербург', country: 'Россия', lat: 59.94, lon: 30.31 },
  { code: 'KZN', name: 'Казань', country: 'Россия', lat: 55.79, lon: 49.12 },
  { code: 'SVX', name: 'Екатеринбург', country: 'Россия', lat: 56.84, lon: 60.6 },
  { code: 'OVB', name: 'Новосибирск', country: 'Россия', lat: 55.03, lon: 82.92 },
  { code: 'AER', name: 'Сочи', country: 'Россия', lat: 43.6, lon: 39.73 },
  { code: 'KRR', name: 'Краснодар', country: 'Россия', lat: 45.04, lon: 38.98 },
  { code: 'KUF', name: 'Самара', country: 'Россия', lat: 53.2, lon: 50.15 },
  { code: 'NQZ', name: 'Астана', country: 'Казахстан', lat: 51.17, lon: 71.43 },
  { code: 'ALA', name: 'Алматы', country: 'Казахстан', lat: 43.24, lon: 76.89 },
  { code: 'MSQ', name: 'Минск', country: 'Беларусь', lat: 53.9, lon: 27.57 },
  { code: 'TAS', name: 'Ташкент', country: 'Узбекистан', lat: 41.3, lon: 69.24 },
  { code: 'FRU', name: 'Бишкек', country: 'Киргизия', lat: 42.87, lon: 74.59 },
]

const KEY = '1surak.departureCity'
const DEFAULT = DEPARTURE_CITIES[0]

export function findDepartureCity(code: string | null): DepartureCity {
  return DEPARTURE_CITIES.find((city) => city.code === code) ?? DEFAULT
}

/** The saved city, or null when the user never picked one (then we detect it). */
export function savedDepartureCity(): DepartureCity | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    if (!raw.startsWith('{')) return DEPARTURE_CITIES.find((c) => c.code === raw) ?? null // saved by the old picker
    const city = JSON.parse(raw) as DepartureCity
    return city.code && city.name ? city : null
  } catch {
    return null
  }
}

export function getDepartureCity(): DepartureCity {
  return savedDepartureCity() ?? DEFAULT
}

export function saveDepartureCity(city: DepartureCity): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(city))
  } catch {
    // Storage full or blocked (private mode): the choice lasts until the page reloads.
  }
}

function distance(a: DepartureCity, b: { lat: number; lon: number }): number {
  if (a.lat === undefined || a.lon === undefined) return Infinity
  const rad = Math.PI / 180
  const x = (b.lon - a.lon) * rad * Math.cos(((a.lat + b.lat) / 2) * rad)
  const y = (b.lat - a.lat) * rad
  return Math.hypot(x, y)
}

export function nearestFirst(cities: DepartureCity[], here: { lat: number; lon: number }): DepartureCity[] {
  return [...cities].sort((a, b) => distance(a, here) - distance(b, here))
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
