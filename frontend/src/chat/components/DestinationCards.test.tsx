import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { DestinationCard } from '@/types/api'
import { DestinationCards } from './DestinationCards'

const base: DestinationCard = {
  id: 'hurghada',
  name: 'Хургада',
  country: 'Египет',
  country_code: 'EG',
  kinds: ['sea'],
  flight_hours: 6.5,
  direct: null,
  train_hours: null,
  visa: 'виза по прибытии',
  visa_easy: true,
  price_level: 1,
  price: 'недорого',
  kids: 'хорошо с детьми',
  kids_fit: 'good',
  climate: null,
  highlights: ['тёплое море'],
  watch_out: ['ветрено'],
  why: 'Тёплое море',
}

const PHOTO = {
  url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Alanya.jpg/960px-Alanya.jpg',
  width: 960,
  height: 640,
  author: 'Jane Doe',
  license: 'CC BY-SA 4.0',
  file_url: 'https://commons.wikimedia.org/wiki/File:Alanya.jpg',
}
const KZT = { code: 'KZT', sign: '₸', glyph: '₸', per_rub: 5.561828 }

function renderCard(card: DestinationCard, currency?: typeof KZT) {
  render(
    <DestinationCards
      widget={{ type: 'destinations', summary: [], cards: [card], currency }}
      canPick={false}
      onPick={() => {}}
      onDetails={() => {}}
    />,
  )
}

const TICKET = {
  price_rub: 13_101,
  airline: 'NE',
  airline_name: 'Nesma Airlines',
  logo: 'https://pics.avs.io/64/64/NE.png',
  flight_number: 'NE 609',
  transfers: 0,
  hours: 5.5,
  departure: '2026-11-07 14:30',
  link: 'https://www.aviasales.ru/search/MOW0711HRG1',
  direct_available: true,
}

describe('DestinationCards', () => {
  it('should mark a city from the route map as not checked by the team', () => {
    renderCard({ ...base, verified: false })

    expect(screen.getByText('не проверено')).toHaveAttribute('title', expect.stringContaining('не из нашего каталога'))
  })

  it('should not mark a catalogue place', () => {
    renderCard(base)

    expect(screen.queryByText('не проверено')).toBeNull()
  })

  it('should show the real photo of the place', () => {
    renderCard({ ...base, photo: PHOTO })

    expect(document.querySelector(`img[src="${PHOTO.url}"]`)).not.toBeNull()
  })

  it('should keep the brief chips in one sideways scrolling row', () => {
    render(
      <DestinationCards
        widget={{ type: 'destinations', summary: ['Море', 'Ноябрь · 2–4 ночи', 'без долгих перелётов'], cards: [base] }}
        canPick={false}
        onPick={() => {}}
        onDetails={() => {}}
      />,
    )

    const row = screen.getByRole('group', { name: 'Подбирал по' })
    expect(row).toHaveClass('scroll-row')
    expect(row).toHaveTextContent('МореНоябрь · 2–4 ночибез долгих перелётов')
  })

  it('should hand the place to the details panel instead of stretching the card', async () => {
    const onDetails = vi.fn()
    render(
      <DestinationCards
        widget={{ type: 'destinations', summary: [], cards: [base], currency: KZT }}
        canPick={false}
        onPick={() => {}}
        onDetails={onDetails}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Подробнее' }))

    expect(onDetails).toHaveBeenCalledWith(base, KZT)
    expect(screen.queryByText('тёплое море')).toBeNull()
  })

  it('should say how the ticket price changed since the last check', () => {
    renderCard({ ...base, flight: TICKET, price_change: { rub: 326, since: '2026-10-19T12:00:00+00:00' } })

    expect(screen.getByText('дороже на 326 ₽ с 19 окт')).toBeInTheDocument()
  })

  it('should keep a price in the agent text on one line', () => {
    renderCard({ ...base, why: 'Билет от 72 504 ₸' })

    expect(screen.getByText(/Билет от/).textContent).toBe('Билет от 72\u00a0504\u00a0₸')
  })

  it('should show the ticket in the currency of the departure city', () => {
    renderCard({ ...base, flight: { ...TICKET, price_rub: 7_707 } }, KZT)

    expect(screen.getByRole('link', { name: /Nesma Airlines/ })).toHaveTextContent(/42\s865 ₸/)
  })

  it('should call a change too small for the currency the same price', () => {
    const usd = { code: 'USD', sign: '$', glyph: '$', per_rub: 0.012416 }
    renderCard({ ...base, flight: TICKET, price_change: { rub: 30, since: '2026-10-19T12:00:00+00:00' } }, usd)

    expect(screen.getByText('цена та же с 19 окт')).toBeInTheDocument()
  })

  it('should say when the ticket got cheaper or stayed the same', () => {
    renderCard({ ...base, flight: TICKET, price_change: { rub: -1_200, since: '2026-10-19T12:00:00+00:00' } })
    expect(screen.getByText(/дешевле на 1\s200 ₽ с 19 окт/)).toBeInTheDocument()
  })

  it('should say whether a known flight is direct', () => {
    renderCard({ ...base, flight_hours: 5, direct: false })

    expect(screen.getByText('5 ч · с пересадкой')).toBeInTheDocument()
  })
})
