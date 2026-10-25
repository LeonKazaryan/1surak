import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DepartureCityPicker } from './DepartureCityPicker'

const WHEREAMI = { iata: 'NQZ', name: 'Астана', country_name: 'Казахстан', coordinates: '71.42:51.14' }
const KAZAN = [{ code: 'KZN', name: 'Казань', country_name: 'Россия', coordinates: { lat: 55.79, lon: 49.12 } }]

function mockApi(whereami: unknown = WHEREAMI) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({ ok: true, json: async () => (url.includes('whereami') ? whereami : KAZAN) })),
  )
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

describe('DepartureCityPicker', () => {
  it('should pick the nearest city by IP on the first visit', async () => {
    mockApi()
    render(<DepartureCityPicker />)

    expect(await screen.findByRole('button', { name: 'Город вылета: Астана' })).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('1surak.departureCity')!)).toMatchObject({ code: 'NQZ' })
  })

  it('should keep a city the user picked before over the detected one', async () => {
    mockApi()
    localStorage.setItem('1surak.departureCity', 'LED')
    render(<DepartureCityPicker />)

    await waitFor(() => expect(fetch).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: 'Город вылета: Санкт-Петербург' })).toHaveTextContent('Петербург')
  })

  it('should list the nearest cities first and find any city by name', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<DepartureCityPicker />)
    await user.click(await screen.findByRole('button', { name: 'Город вылета: Астана' }))

    const options = screen.getAllByRole('option').map((o) => o.textContent)
    expect(options[0]).toContain('рядом с вами')
    expect(options[1]).toContain('Новосибирск') // the neighbours of Astana come first
    expect(options.join()).toContain('Алматы')
    expect(options.join()).not.toContain('Минск') // too far to suggest

    await user.type(screen.getByRole('textbox', { name: 'Поиск города вылета' }), 'каз')
    await user.click(await screen.findByRole('option', { name: /Казань/ }))

    expect(screen.getByRole('button', { name: 'Город вылета: Казань' })).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('1surak.departureCity')!)).toMatchObject({ code: 'KZN', name: 'Казань' })
  })
})
