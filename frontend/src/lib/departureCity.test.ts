import { beforeEach, describe, expect, it, vi } from 'vitest'
import { departureCityKnown, getDepartureCity, onDepartureCityChange, saveDepartureCity } from './departureCity'

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('departureCity', () => {
  it('should default to Moscow when nothing is saved', () => {
    expect(getDepartureCity().name).toBe('Москва')
  })

  it('should read back the saved city', () => {
    saveDepartureCity({ code: 'KZN', name: 'Казань' })

    expect(getDepartureCity()).toMatchObject({ code: 'KZN', name: 'Казань' })
  })

  it('should fall back to Moscow when the saved value is broken', () => {
    localStorage.setItem('1surak.departureCity', '{"code":"astana"}')

    expect(getDepartureCity().name).toBe('Москва')
  })

  it('should fall back to Moscow when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(getDepartureCity().name).toBe('Москва')
  })

  it('should know when the city is only the Moscow fallback', () => {
    expect(departureCityKnown()).toBe(false)

    saveDepartureCity({ code: 'KZN', name: 'Казань' })

    expect(departureCityKnown()).toBe(true)
  })

  it('should tell every picker when the city changes', () => {
    const seen: string[] = []
    const stop = onDepartureCityChange((city) => seen.push(city.code))

    saveDepartureCity({ code: 'ALA', name: 'Алматы' })
    stop()
    saveDepartureCity({ code: 'KZN', name: 'Казань' })

    expect(seen).toEqual(['ALA'])
  })
})
