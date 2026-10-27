import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { BookingEvent, TripPlanEvent } from '@/types/api'
import { formatMoney } from '../widgets'
import { BookingCard } from './BookingCard'
import { TripPlan } from './TripPlan'
import { PLAN } from './testPlan'

const KZT = { code: 'KZT', sign: '₸', glyph: '₸', per_rub: 5.561828 }
/** A price as the text matchers see it: they turn the no-break spaces into plain ones. */
const money = (rub: number, currency?: typeof KZT) => formatMoney(rub, currency).replace(/\s/g, ' ')
const BOOKING: BookingEvent = {
  type: 'booking',
  number: '1S-ABC234',
  plan_message_id: 'm1',
  name: 'Анталья',
  dates: PLAN.dates,
  holder: 'Анна Смирнова',
  extras: [{ id: 'early_check_in:antalya-h1', type: 'early_check_in', label: 'Ранний заезд', price_rub: 3200 }],
  total_rub: PLAN.costs.total + 3200,
  currency: PLAN.currency,
}

function renderPlan(props: Partial<Parameters<typeof TripPlan>[0]> = {}, plan: TripPlanEvent = PLAN) {
  const onAsk = vi.fn()
  const onBook = vi.fn().mockResolvedValue(BOOKING)
  render(<TripPlan plan={plan} canAct onAsk={onAsk} onBook={onBook} {...props} />)
  return { onAsk, onBook, card: screen.getByRole('article', { name: 'План поездки: Анталья' }) }
}

describe('TripPlan', () => {
  it('should open with the place, the dates and who is going', () => {
    const { card } = renderPlan()

    expect(within(card).getByRole('heading', { name: 'Анталья' })).toBeInTheDocument()
    expect(within(card).getByText('6–13 ноября · 7 ночей · 2 взрослых, ребёнок 5 лет')).toBeInTheDocument()
  })

  it('should show the real photo with its author in the tooltip, not written over it', () => {
    const { card } = renderPlan()

    const photo = PLAN.stops[0].photo!
    expect(card.querySelector(`img[src="${photo.url}"]`)).toHaveAttribute('title', 'Фото: Jane Doe, CC BY-SA 4.0')
    expect(within(card).queryByText(/^Фото: Jane Doe/)).toBeNull()
  })

  it('should list the flights with local times and the connection checks', () => {
    renderPlan()

    const road = screen.getByRole('region', { name: 'Дорога' })
    expect(within(road).getByText('Москва → Анталья')).toBeInTheDocument()
    expect(within(road).getByText(/09:40 → 13:40/)).toBeInTheDocument()
    expect(within(road).getAllByText(/Аэрофлот/)).toHaveLength(2)
    expect(within(road).getByText('Прилёт 13:40, заселение с 14:00')).toBeInTheDocument()
    const buy = within(road).getAllByRole('link', { name: /Купить билет .* на Aviasales/ })
    expect(buy.map((a) => a.getAttribute('href'))).toEqual(['https://www.aviasales.ru/t', 'https://www.aviasales.ru/t'])
    buy.forEach((a) => expect(a).toHaveAttribute('target', '_blank'))
  })

  it('should show a real hotel without inventing its rating or terms, and offer more hotels', async () => {
    const stop = PLAN.stops[0]
    const real = {
      ...stop.hotel,
      rating: null,
      reviews: null,
      demo: false,
      real: true,
      stars_known: true,
      price_estimate: true,
      terms_known: false,
      source_url: 'https://www.wikidata.org/wiki/Q1',
      maps_url: 'https://www.google.com/maps/search/H/@36.8,30.7,17z',
      photo: { url: 'https://upload.wikimedia.org/h.jpg', width: 640, height: 400, author: 'Анна', license: 'CC BY 4.0', file_url: 'https://commons.wikimedia.org/wiki/File:H.jpg' },
    }
    const { onAsk } = renderPlan({}, { ...PLAN, stops: [{ ...stop, hotel: real }, ...PLAN.stops.slice(1)] })

    const stay = screen.getByRole('region', { name: 'Где живёте' })
    expect(within(stay).getByText('цена ориентировочная')).toBeInTheDocument()
    // unknown terms are said once, by the badge, and no meal plan is promised
    expect(within(stay).getByText('цена ориентировочная')).toHaveAttribute('title', expect.stringMatching(/условия уточним/))
    const label = real.meal_label[0].toUpperCase() + real.meal_label.slice(1)
    expect(within(stay).queryByText(label, { exact: true })).toBeNull()
    expect(within(stay).queryByText(/отзыв/)).toBeNull()
    expect(within(stay).getByRole('link', { name: 'Анна, CC BY 4.0' })).toBeInTheDocument()
    // the map is Google's, where the reviews are, not the Wikidata entry it was found in
    expect(within(stay).getByRole('link', { name: 'на карте' })).toHaveAttribute('href', real.maps_url)
    await userEvent.click(within(stay).getByRole('button', { name: 'Ещё отели' }))
    expect(onAsk).toHaveBeenCalledWith(`Покажи ещё отели: ${stop.name}`)
  })

  it('should show each wish with the proof word for word and its source, and which ones are not confirmed', () => {
    const stop = PLAN.stops[0]
    const sea = { wish: 'с видом на море', verdict: 'yes' as const, quote: 'Потрясающий вид на море открывается с балкона', note: null, source: 'otzovik.com', source_url: 'https://otzovik.com/r' }
    const hotel = {
      ...stop.hotel,
      evidence: [
        sea,
        { wish: 'можно с собакой', verdict: 'yes' as const, quote: 'Размещение с животными до 5 кг', note: 'до 5 кг, 1000 ₽ в сутки', source: 'сайт отеля', source_url: 'https://hotel.example' },
        { wish: 'с ванной', verdict: 'unknown' as const, quote: null, note: null, source: null, source_url: null },
      ],
    }
    const alternative = { ...stop.alternatives[0], evidence: [sea] }
    renderPlan({}, { ...PLAN, stops: [{ ...stop, hotel, alternatives: [alternative] }, ...PLAN.stops.slice(1)] })

    const proof = screen.getByRole('list', { name: 'Ваши пожелания' })
    expect(within(proof).getByText('С видом на море')).toBeInTheDocument()
    expect(within(proof).getByText('«Потрясающий вид на море открывается с балкона»')).toBeInTheDocument()
    expect(within(proof).getByRole('link', { name: 'otzovik.com' })).toHaveAttribute('href', 'https://otzovik.com/r')
    expect(within(proof).getByText('до 5 кг, 1000 ₽ в сутки')).toBeInTheDocument()
    expect(within(proof).getByRole('link', { name: 'сайт отеля' })).toHaveAttribute('href', 'https://hotel.example')
    expect(within(proof).getByText('С ванной')).toBeInTheDocument()
    expect(within(proof).getByText('не нашёл подтверждения')).toBeInTheDocument()
    const others = screen.getByRole('list', { name: 'Другие варианты' })
    expect(within(others).getByText(/с видом на море/)).toBeInTheDocument()
  })

  it('should not call real hotels a demo at checkout, only their price an estimate', () => {
    const stop = PLAN.stops[0]
    renderPlan({}, { ...PLAN, stops: [{ ...stop, hotel: { ...stop.hotel, real: true, demo: false } }, ...PLAN.stops.slice(1)] })

    expect(screen.getByText('Цены отелей ориентировочные, оплата имитируется')).toBeInTheDocument()
    expect(screen.queryByText(/Отели демонстрационные/)).toBeNull()
  })

  it('should explain the hotel pick, offer the alternative and say what it ruled out', async () => {
    const { onAsk } = renderPlan()

    const stay = screen.getByRole('region', { name: 'Где живёте' })
    expect(within(stay).getByRole('heading', { name: 'Морской бриз' })).toBeInTheDocument()
    expect(within(stay).getAllByText('демо')[0]).toBeInTheDocument()
    expect(within(stay).getByText('детский клуб')).toBeInTheDocument()
    expect(within(stay).getByText(/Солнечная терраса/)).toHaveTextContent('только для взрослых, а с вами ребёнок')

    await userEvent.click(within(stay).getByRole('button', { name: 'Выбрать «Дом у маяка»' }))
    expect(onAsk).toHaveBeenCalledWith('Хочу отель «Дом у маяка» вместо «Морской бриз»')
  })

  it('should walk through the trip day by day', async () => {
    renderPlan()

    const days = screen.getByRole('region', { name: 'По дням' })
    expect(within(days).getByText('Перелёт Москва → Анталья')).toBeInTheDocument()

    await userEvent.click(within(days).getByRole('button', { name: 'суббота, 7 ноября' }))

    expect(within(days).getByRole('button', { name: 'суббота, 7 ноября' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(days).getAllByText('Калеичи').length).toBeGreaterThan(0)
    expect(within(days).getAllByTitle(/Jane Doe/).length).toBeGreaterThan(0)
    expect(within(days).getByText('Пияз')).toBeInTheDocument()
    const onMap = within(days).getByRole('link', { name: 'Калеичи' })
    expect(onMap.getAttribute('href')).toMatch(/^https:\/\/www\.google\.com\/maps\/search\/.+\/@36\.884,30\.705,17z$/)
    expect(onMap).toHaveAttribute('target', '_blank')
  })

  it('should credit the guide the days are drawn from', () => {
    renderPlan()

    const days = screen.getByRole('region', { name: 'По дням' })
    expect(within(days).getByText(/^Фото: Wikimedia Commons · тексты:/)).toHaveTextContent('Фото: Wikimedia Commons · тексты: Викигид, CC BY-SA')
    expect(within(days).getByRole('link', { name: 'Викигид' })).toHaveAttribute('href', PLAN.stops[0].source_url)
  })

  it('should credit OpenStreetMap on a day that eats at a place from it', () => {
    const [first, ...rest] = PLAN.days
    const spot = PLAN.days.flatMap((d) => d.items).find((i) => i.spot)!.spot!
    const osm = { kind: 'food' as const, title: 'Обед: Der Garten', time: '13:30', note: null, spot: { ...spot, id: 'osm-n1', photo: null } }
    renderPlan({}, { ...PLAN, days: [{ ...first, items: [osm] }, ...rest] })

    const days = screen.getByRole('region', { name: 'По дням' })
    expect(within(days).getByRole('link', { name: '© участники OpenStreetMap' })).toHaveAttribute('href', 'https://www.openstreetmap.org/copyright')
  })

  it('should not credit the guide on a day that uses nothing from it', () => {
    const stop = { ...PLAN.stops[0], dishes: [], food_intro: null }
    renderPlan({}, { ...PLAN, stops: [stop] })

    const days = screen.getByRole('region', { name: 'По дням' })
    expect(within(days).queryByRole('link', { name: 'Викигид' })).toBeNull()
  })

  it('should add up the bill in the user currency', () => {
    renderPlan({}, { ...PLAN, currency: KZT })

    const bill = screen.getByRole('region', { name: 'Стоимость' })
    expect(within(bill).getByText(money(PLAN.costs.total, KZT))).toBeInTheDocument()
    expect(within(bill).getByText(money(PLAN.costs.flights, KZT))).toBeInTheDocument()
    expect(within(bill).getByText(`${money(PLAN.costs.per_person, KZT)} на человека`)).toBeInTheDocument()
  })

  it('should not call the trip in budget before the flights are counted', () => {
    renderPlan({}, { ...PLAN, costs: { ...PLAN.costs, flights: 0, flights_complete: false, budget: 400_000 } })

    const bill = screen.getByRole('region', { name: 'Стоимость' })
    expect(within(bill).getByText(/^Пока без перелётов/)).toBeInTheDocument()
    expect(within(bill).queryByText(/В бюджете/)).toBeNull()
  })

  it('should say what changed and what it could not find', () => {
    renderPlan({}, { ...PLAN, changes: ['Даты: 8–15 ноября вместо 6–13 ноября'], unmet: ['Отелей с животными здесь не нашлось'] })

    expect(screen.getByRole('region', { name: 'Что изменилось' })).toHaveTextContent('Даты: 8–15 ноября вместо 6–13 ноября')
    expect(screen.getByRole('region', { name: 'Чего не нашёл' })).toHaveTextContent('Отелей с животными здесь не нашлось')
  })

  it('should check out with the chosen extras and show the booking number', async () => {
    const { onBook } = renderPlan()

    await userEvent.click(screen.getByRole('button', { name: /Оформить поездку/ }))
    const sheet = await screen.findByRole('dialog', { name: 'Оформление поездки' })
    await userEvent.click(within(sheet).getByRole('checkbox', { name: /Ранний заезд/ }))
    await userEvent.type(within(sheet).getByLabelText('Имя и фамилия'), 'Анна Смирнова')
    await userEvent.click(within(sheet).getByRole('button', { name: `Оплатить ${formatMoney(PLAN.costs.total + 3200)}` }))

    expect(onBook).toHaveBeenCalledWith(['early_check_in:antalya-h1'], 'Анна Смирнова')
    expect(await within(sheet).findByText('Поездка оформлена')).toBeInTheDocument()
    expect(within(sheet).getByText('1S-ABC234')).toBeInTheDocument()
  })

  it('should offer each city its own extra on a two-city trip', async () => {
    const [check] = PLAN.checks.filter((c) => c.fix)
    const other = { ...check, fix: { ...check.fix!, id: 'early_check_in:alanya-h2', label: 'Ранний заезд в «Маяк»', price_rub: 2500 } }
    const { onBook } = renderPlan({}, { ...PLAN, checks: [...PLAN.checks, other] })

    await userEvent.click(screen.getByRole('button', { name: /Оформить поездку/ }))
    const sheet = await screen.findByRole('dialog', { name: 'Оформление поездки' })
    await userEvent.click(within(sheet).getByRole('checkbox', { name: /«Морской бриз»/ }))
    await userEvent.click(within(sheet).getByRole('checkbox', { name: /«Маяк»/ }))
    await userEvent.type(within(sheet).getByLabelText('Имя и фамилия'), 'Анна Смирнова')
    await userEvent.click(within(sheet).getByRole('button', { name: `Оплатить ${formatMoney(PLAN.costs.total + 3200 + 2500)}` }))

    expect(onBook).toHaveBeenCalledWith(['early_check_in:antalya-h1', 'early_check_in:alanya-h2'], 'Анна Смирнова')
  })

  it('should not pay without a name', async () => {
    const { onBook } = renderPlan()

    await userEvent.click(screen.getByRole('button', { name: /Оформить поездку/ }))
    const sheet = await screen.findByRole('dialog', { name: 'Оформление поездки' })
    await userEvent.click(within(sheet).getByRole('button', { name: /Оплатить/ }))

    expect(onBook).not.toHaveBeenCalled()
    expect(within(sheet).getByText('Укажите имя и фамилию, как в паспорте')).toBeInTheDocument()
  })

  it('should show a booked plan as done and offer no second checkout', () => {
    const { card } = renderPlan({ booking: BOOKING })

    expect(within(card).getByText(/Оформлено/)).toHaveTextContent('1S-ABC234')
    expect(within(card).queryByRole('button', { name: /Оформить поездку/ })).toBeNull()
  })

  it('should keep an older plan read only', () => {
    const { card } = renderPlan({ canAct: false })

    expect(within(card).getByRole('button', { name: 'Выбрать «Дом у маяка»' })).toBeDisabled()
    expect(within(card).queryByRole('button', { name: /Оформить поездку/ })).toBeNull()
  })
})

describe('BookingCard', () => {
  it('should show the booking number, the trip and the total', () => {
    render(<BookingCard booking={BOOKING} />)

    const card = screen.getByRole('article', { name: 'Бронь 1S-ABC234' })
    expect(card).toHaveTextContent('Анталья')
    expect(card).toHaveTextContent('6–13 ноября')
    expect(card).toHaveTextContent(money(BOOKING.total_rub))
    expect(card).toHaveTextContent('Ранний заезд')
  })
})
