export interface DepartureCity {
  code: string
  name: string
  short?: string
}

export const DEPARTURE_CITIES: DepartureCity[] = [
  { code: 'MOW', name: 'Москва' },
  { code: 'LED', name: 'Санкт-Петербург', short: 'Петербург' },
  { code: 'KZN', name: 'Казань' },
  { code: 'SVX', name: 'Екатеринбург' },
  { code: 'OVB', name: 'Новосибирск' },
  { code: 'AER', name: 'Сочи' },
  { code: 'KRR', name: 'Краснодар' },
  { code: 'KUF', name: 'Самара' },
]

const KEY = '1surak.departureCity'

export function findDepartureCity(code: string | null): DepartureCity {
  return DEPARTURE_CITIES.find((city) => city.code === code) ?? DEPARTURE_CITIES[0]
}

export function getDepartureCity(): DepartureCity {
  try {
    return findDepartureCity(localStorage.getItem(KEY))
  } catch {
    return DEPARTURE_CITIES[0]
  }
}

export function saveDepartureCity(code: string): void {
  try {
    localStorage.setItem(KEY, code)
  } catch {
    // Storage full or blocked (private mode): the choice lasts until the page reloads.
  }
}
