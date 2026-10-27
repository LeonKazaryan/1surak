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
  it('should not mark any place as not checked', () => {
    renderCard(base)

    expect(screen.queryByText('не проверено')).toBeNull()
  })

  it('should credit Open-Meteo for the weather, as its licence asks', () => {
    renderCard({ ...base, climate: { month: 'ноябрь', month_in: 'ноябре', day: 27, sea: 26 } })

    expect(screen.getByRole('link', { name: 'Open-Meteo' })).toHaveAttribute('href', 'https://open-meteo.com/')
  })

  it('should not credit a weather source when no card shows the weather', () => {
    renderCard(base)

    expect(screen.queryByRole('link', { name: 'Open-Meteo' })).toBeNull()
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

describe('a place with no cached ticket', () => {
  it('should offer two tickets through the main airport and the live search on Aviasales', () => {
    renderCard({
      ...base,
      flight: null,
      search_link: 'https://www.aviasales.ru/search/NQZ1512MQX1',
      flight_via: { via: 'Аддис-Абеба', via_in: 'Аддис-Абебе', price_rub: 78_100, estimate: true, tickets: [] },
    })

    expect(screen.getByText(/≈ от 78\s100 ₽/)).toBeInTheDocument()
    expect(screen.getByText(/с пересадкой в Аддис-Абебе, два билета/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Найти билеты на Aviasales/ })).toHaveAttribute('href', 'https://www.aviasales.ru/search/NQZ1512MQX1')
    expect(screen.queryByText('билетов не нашлось')).toBeNull()
  })
})

describe('DestinationCards layout', () => {
  it('should widen the last of an odd number of places so no cell stays empty', () => {
    const names = ['Берлин', 'Мюнхен', 'Ницца']
    render(
      <DestinationCards
        widget={{ type: 'destinations', summary: [], cards: names.map((name, i) => ({ ...base, id: `p${i}`, name })) }}
        canPick={false}
        onPick={() => {}}
        onDetails={() => {}}
      />,
    )

    const card = (name: string) => screen.getByRole('heading', { name }).closest('article')!
    expect(card('Ницца').className).toContain('sm:col-span-2')
    expect(card('Берлин').className).not.toContain('sm:col-span-2')
  })
})
