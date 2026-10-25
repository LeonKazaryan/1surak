import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getDepartureCity, saveDepartureCity } from './departureCity'

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

  it('should fall back to Moscow when the saved code is unknown', () => {
    localStorage.setItem('1surak.departureCity', 'XXX')

    expect(getDepartureCity().name).toBe('Москва')
  })

  it('should fall back to Moscow when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(getDepartureCity().name).toBe('Москва')
  })
})
