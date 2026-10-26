import { describe, expect, it } from 'vitest'
import { forPassengers } from './ticketFormat'

const LINK = 'https://www.aviasales.ru/search/NQZ3010KZN1?t=N4179'

describe('forPassengers', () => {
  it('should open Aviasales for the whole party', () => {
    expect(forPassengers(LINK, 2)).toBe('https://www.aviasales.ru/search/NQZ3010KZN2?t=N4179')
  })

  it('should leave the link alone for one passenger or an unknown format', () => {
    expect(forPassengers(LINK, 1)).toBe(LINK)
    expect(forPassengers('https://www.aviasales.ru/other', 3)).toBe('https://www.aviasales.ru/other')
  })
})
