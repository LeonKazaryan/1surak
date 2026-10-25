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
  return savedDepartureCity() ?? FALLBACK_CITY
}

export function saveDepartureCity(city: DepartureCity): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(city))
  } catch {
    // Storage full or blocked (private mode): the choice lasts until the page reloads.
  }
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
