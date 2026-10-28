import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { RouteCard } from '@/types/api'
import { RouteCardView } from './RouteCard'
import { RouteDetails } from './RouteDetails'
import { SMART_ROUTE } from './testRoute'

const money = (text: string) => new RegExp(text.replace(/ /g, '\\s'))

describe('RouteDetails with smarter ways', () => {
  it('should show a smart way as its parts, with the train and where to buy it', () => {
    render(<RouteDetails card={SMART_ROUTE} />)

    const way = screen.getByRole('list', { name: 'Алматы → Самарканд через Ташкент' })
    expect(within(way).getByRole('link', { name: 'Алматы → Ташкент, Uzbekistan Airways' })).toHaveAttribute(
      'href',
      expect.stringContaining('aviasales.ru/search/ALA1805TAS1'),
    )
    const train = within(way).getByRole('link', { name: 'Ташкент → Самарканд, Поезд 776Ф' })
    expect(train).toHaveAttribute('href', 'https://www.tutu.ru/poezda/rasp_d.php?nnst1=2900000&nnst2=2900700')
    expect(train).toHaveTextContent('13:56 → 16:09')
    expect(within(way).getByText('пересадка в Ташкент')).toBeInTheDocument()
    expect(screen.getAllByText(/Умный путь через Ташкент/)).toHaveLength(2)
  })

  it('should strike the direct way through and show the saving', () => {
    render(<RouteDetails card={SMART_ROUTE} />)

    expect(screen.getByText(money('−25 191 ₽'))).toBeInTheDocument()
    expect(screen.getByText(/вместо Turkish Airlines, 1 пересадка, 10,5 ч/)).toBeInTheDocument()
    expect(screen.getByText(money('37 089 ₽')).closest('del')).not.toBeNull()
  })

  it('should keep each city after the leg that reaches it and count the trains in the total', () => {
    render(<RouteDetails card={SMART_ROUTE} />)

    const steps = [...screen.getByRole('list', { name: 'Маршрут' }).children].map((li) => li.textContent)
    expect(steps).toEqual([
      expect.stringContaining('Астана → Алматы'),
      expect.stringContaining('Алматы'),
      expect.stringContaining('Алматы → Самарканд'),
      expect.stringContaining('Самарканд'),
      expect.stringContaining('Самарканд → Астана'),
    ])
    expect(screen.getByText(money('в том числе поезда и автобусы на 5 061 ₽'))).toBeInTheDocument()
    expect(screen.getByText(money('Умные пересадки сберегли 63 197 ₽'), { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Даты состыкованы: 12 мая → 18 мая → 21 мая')).toBeInTheDocument()
  })
})

describe('RouteCardView', () => {
  it('should fit a tour of six cities into one banner', () => {
    const names = ['Бангкок', 'Паттайя', 'Пхукет', 'Краби', 'Фукуок', 'Нячанг']
    const stops = names.map((name, i) => ({ ...SMART_ROUTE.stops[0], id: `s${i}`, name, nights: 2 }))
    const card: RouteCard = {
      ...SMART_ROUTE,
      stops,
      legs: [...names, null].map((to, i) => ({
        from: i ? names[i - 1] : 'Астана',
        to: to ?? 'Астана',
        mode: 'flight' as const,
        km: 900,
        hours: 2,
        from_stop: i ? i - 1 : null,
        to_stop: to ? i : null,
      })),
    }
    const props = { best: false, picked: false, dimmed: false, canPick: true, onPick: () => {}, detailsOpen: false, onDetails: () => {} }

    render(<RouteCardView card={card} {...props} />)

    expect(screen.getAllByRole('heading').map((h) => h.textContent)).toEqual(names)
    expect(screen.getByText(/6 городов · 12/)).toBeInTheDocument()
  })
})

describe('Yandex.Rasp credit', () => {
  const credit = { text: 'Данные предоставлены сервисом Яндекс.Расписания', link: 'https://rasp.yandex.ru/' }
  const [out, there, home] = SMART_ROUTE.legs
  const parts = there.parts!.map((p) => (p.ground ? { ...p, ground: { ...p.ground, credit, link: 'https://rasp.yandex.ru/search/?fromId=c10335&toId=c10334' } } : p))
  const card: RouteCard = { ...SMART_ROUTE, legs: [out, { ...there, parts }, home] }

  it('should credit Yandex right under the ride it gave and once on the card', () => {
    render(<RouteDetails card={card} />)
    const way = screen.getByRole('list', { name: 'Алматы → Самарканд через Ташкент' })
    expect(within(way).getByRole('link', { name: credit.text })).toHaveAttribute('href', 'https://rasp.yandex.ru/')
  })

  it('should not credit Yandex where none of its data is shown', () => {
    render(<RouteDetails card={SMART_ROUTE} />)
    expect(screen.queryByRole('link', { name: credit.text })).toBeNull()
  })
})

describe('RouteDetails without a fare on the day', () => {
  const [out, there, home] = SMART_ROUTE.legs
  const { ticket, ...unpriced } = out

  it('should price the flight by the nearest dates and open the live search for the day', () => {
    const guided = { ...unpriced, guide: { ...ticket!, price_rub: 6_100 }, date: '2027-05-12', search_link: 'https://www.aviasales.ru/search/NQZ1205ALA1' }
    render(<RouteDetails card={{ ...SMART_ROUTE, legs: [guided, there, home], total_complete: false, total_guided: true }} />)

    const row = screen.getByRole('link', { name: 'Астана → Алматы, цены в поиске Aviasales' })
    expect(row).toHaveAttribute('href', 'https://www.aviasales.ru/search/NQZ1205ALA1')
    expect(row).toHaveTextContent('ориентир по ближайшим датам')
    expect(row).toHaveTextContent(money('~6 100 ₽'))
    expect(screen.getByText('часть перелётов по ориентиру ближайших дат')).toBeInTheDocument()
  })

  it('should mark a ticket dearer than the route usually is', () => {
    render(<RouteDetails card={{ ...SMART_ROUTE, legs: [{ ...out, usual_rub: 2_500 }, there, home] }} />)

    expect(screen.getByRole('link', { name: 'Астана → Алматы, FlyArystan' })).toHaveTextContent('дороже обычного')
  })
})

describe('RouteCard visas', () => {
  it('should show one chip for a visa several countries of the route share', () => {
    const visa = {
      rule: 'visa_required' as const,
      label: 'нужна виза',
      text: 'Для граждан Казахстана нужна шенгенская виза, одна на Италию, Испанию и Португалию.',
      days: null,
      pair: 'KZ-ES',
      fee: null,
      name: 'Шенген',
      countries: ['Италия', 'Испания', 'Португалия'],
    }
    const props = { best: false, picked: false, dimmed: false, canPick: true, onPick: () => {}, detailsOpen: false, onDetails: () => {} }
    render(<RouteCardView card={{ ...SMART_ROUTE, visas: [visa] }} {...props} />)

    const chips = within(screen.getByRole('list', { name: 'Визы' })).getAllByRole('button')
    expect(chips.map((c) => c.textContent)).toEqual(['Шенген: нужна виза'])
  })
})

