import { describe, expect, it } from 'vitest'
import type { GroundRide } from '@/types/api'
import { knownFare, rideTimes, saving, stopIndexAfter, travelDays, units } from './legFormat'
import { SMART_ROUTE } from './testRoute'

const [out, there, home] = SMART_ROUTE.legs

describe('smart ways', () => {
  it('should count the parts of a smart way, not the leg', () => {
    expect(units(there).map((p) => p.mode)).toEqual(['flight', 'ground'])
    expect(units(out)).toEqual([out])
    expect(knownFare(there)).toBe(8_224 + 3_674)
  })

  it('should save what the direct way cost above the smart one', () => {
    expect(saving(there)).toBe(37_089 - 11_898)
    expect(saving(out)).toBeNull()
  })

  it('should list the days of every ticket, the parts of a smart way included', () => {
    expect(travelDays(SMART_ROUTE.legs)).toEqual(['12 мая', '18 мая', '21 мая'])
  })

  it('should place each city after the leg that reaches it', () => {
    expect(SMART_ROUTE.legs.map((leg, i) => stopIndexAfter(leg, i, 2))).toEqual([0, 1, null])
    expect(stopIndexAfter({ ...home, to_stop: undefined }, 1, 2)).toBe(1) // a card saved before `to_stop`
  })
})

describe('rideTimes', () => {
  const ride: GroundRide = { mode: 'train', source: 'Туту.ру', name: 'Поезд 123Ф', hours: 4, link: '/t', departs: '00:33', arrives: '04:48' }

  it('should read a timetable by the clock', () => {
    expect(rideTimes(ride)).toBe('00:33 → 04:48')
  })

  it('should give the day of a bus that runs on a date', () => {
    expect(rideTimes({ ...ride, dated: true, departs: '2026-11-15T00:45:00+03:00', arrives: '2026-11-15T12:15:00+03:00' })).toBe(
      '15 ноя, 00:45 → 12:15',
    )
  })
})
