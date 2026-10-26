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

  it('should ask for the picked hotel by name', async () => {
    const onPick = vi.fn()
    render(<HotelOptionsCards widget={WIDGET} canPick onPick={onPick} />)

    await userEvent.click(screen.getByRole('button', { name: 'Выбрать «Ногай»' }))

    expect(onPick).toHaveBeenCalledWith('Ногай')
  })
})
