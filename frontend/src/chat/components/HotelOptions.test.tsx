import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { HotelOption, HotelOptionsEvent } from '@/types/api'
import { HotelOptionsCards } from './HotelOptions'

const hotel = (over: Partial<HotelOption>): HotelOption => ({
  id: 'kazan-hq1',
  name: 'Ногай',
  stars: 4,
  stars_known: true,
  area: 'в центре',
  photo: null,
  source_url: 'https://www.wikidata.org/wiki/Q1',
  real: true,
  meal_label: 'завтраки',
  night_rub: 7000,
  total_rub: 21000,
  price_estimate: true,
  terms_known: false,
  current: false,
  ...over,
})

const WIDGET: HotelOptionsEvent = {
  type: 'hotel_options',
  place: 'Казань',
  check_in: '2026-11-06',
  nights: 3,
  guests: 2,
  hotels: [
    hotel({ current: true, name: 'Шаляпин Палас', id: 'kazan-hq2' }),
    hotel({
      photo: { url: 'https://upload.wikimedia.org/x.jpg', width: 640, height: 400, author: 'Иван', license: 'CC BY-SA 4.0', file_url: 'https://commons.wikimedia.org/wiki/File:X.jpg' },
    }),
  ],
}

describe('HotelOptionsCards', () => {
  it('should show real hotels with an estimated price, their photo credit and the one in the plan', () => {
    render(<HotelOptionsCards widget={WIDGET} canPick onPick={() => {}} />)

    expect(screen.getAllByText('цена ориентировочная')).toHaveLength(2)
    expect(screen.getAllByText(/около 21\s000 ₽/)).toHaveLength(2)
    expect(screen.getByText('В плане')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Иван, CC BY-SA 4.0' })).toHaveAttribute('href', 'https://commons.wikimedia.org/wiki/File:X.jpg')
    expect(screen.queryByText(/завтраки/)).toBeNull() // the meal plan is not known yet: not claimed
  })

  it('should show a live offer: the photos, the room, the rating and the refund deadline, no «около»', () => {
    const live = hotel({
      price_estimate: false,
      terms_known: true,
      rating: 9.4,
      reviews: 841,
      photos: ['https://static.cupid.travel/rooms/1.jpg', 'https://static.cupid.travel/hotels/1.jpg'],
      room: { name: 'Guest room, 1 King, Ocean view', size_m2: 41, beds: null, view: 'вид на океан', amenities: [], photos: 1 },
      cancel_until: '2026-12-07',
      live_price: true,
      sandbox: false,
    })
    render(<HotelOptionsCards widget={{ ...WIDGET, hotels: [live] }} canPick onPick={() => {}} />)

    expect(screen.getByRole('button', { name: 'Фото 1 из 2, ваш номер: открыть' })).toBeInTheDocument()
    expect(screen.getByText('Guest room, 1 King, Ocean view').parentElement).toHaveTextContent('· 41 м² · вид на океан')
    expect(screen.getByText('9,4')).toHaveAttribute('title', '841 отзыв')
    expect(screen.getByText('Бесплатная отмена до 7 декабря')).toBeInTheDocument()
    expect(screen.queryByText(/около/)).toBeNull()
    expect(screen.queryByText('цена ориентировочная')).toBeNull()
    expect(screen.queryByText(/LiteAPI/)).toBeNull()
  })

  it('should ask for the picked hotel by name', async () => {
    const onPick = vi.fn()
    render(<HotelOptionsCards widget={WIDGET} canPick onPick={onPick} />)

    await userEvent.click(screen.getByRole('button', { name: 'Выбрать «Ногай»' }))

    expect(onPick).toHaveBeenCalledWith('Ногай')
  })

  it('should show which wishes real sources confirm, with the quote on hover, and which they do not', () => {
    const checked = hotel({
      evidence: [
        { wish: 'с видом на море', verdict: 'yes', quote: 'Окна выходят на море', note: null, source: 'otzovik.com', source_url: 'https://otzovik.com/r' },
        { wish: 'с ванной', verdict: 'unknown', quote: null, note: null, source: null, source_url: null },
      ],
    })
    render(<HotelOptionsCards widget={{ ...WIDGET, hotels: [checked] }} canPick onPick={() => {}} />)

    expect(screen.getByText('с видом на море')).toHaveAttribute('title', '«Окна выходят на море», otzovik.com')
    expect(screen.getByText('Не подтверждено: с ванной')).toBeInTheDocument()
  })
})
