import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { DestinationCard } from '@/types/api'
import { DetailsPanel } from './DetailsPanel'
import { PlaceDetails } from './PlaceDetails'

const PHOTO = {
  url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Alanya.jpg/960px-Alanya.jpg',
  width: 960,
  height: 640,
  author: 'Jane Doe',
  license: 'CC BY-SA 4.0',
  file_url: 'https://commons.wikimedia.org/wiki/File:Alanya.jpg',
}
const KZT = { code: 'KZT', sign: '₸', glyph: '₸', per_rub: 5.561828 }

const place: DestinationCard = {
  id: 'alanya',
  name: 'Аланья',
  country: 'Турция',
  country_code: 'TR',
  kinds: ['sea'],
  flight_hours: 5.5,
  direct: true,
  visa: 'без визы',
  visa_easy: true,
  price_level: 1,
  price: 'недорого',
  kids: 'хорошо с детьми',
  kids_fit: 'good',
  climate: { month: 'ноябрь', month_in: 'ноябре', day: 22, night: 14, sea: 24, rain_days: 5 },
  highlights: ['пляж Клеопатры'],
  watch_out: ['вечером прохладно'],
  why: 'Прямой рейс 5,5 ч',
  tradeoff: 'От аэропорта Антальи около 2 часов',
  flight: {
    price_rub: 11_110,
    airline: 'PC',
    airline_name: 'Pegasus Airlines',
    logo: 'https://pics.avs.io/64/64/PC.png',
    flight_number: 'PC 1',
    transfers: 0,
    hours: 5.5,
    departure: '2026-11-06 09:00',
    link: 'https://www.aviasales.ru/search/NQZ0611AYT1',
    direct_available: true,
  },
}

function renderDetails(onClose = vi.fn()) {
  render(
    <DetailsPanel title={place.name} currency={KZT} onClose={onClose}>
      <PlaceDetails card={place} />
    </DetailsPanel>,
  )
  return onClose
}

describe('PlaceDetails', () => {
  it('should show the weather of the trip month', () => {
    renderDetails()

    const weather = screen.getByRole('list', { name: 'Погода в ноябре' })
    expect(weather).toHaveTextContent('Днём+22°')
    expect(weather).toHaveTextContent('Ночью+14°')
    expect(weather).toHaveTextContent('Море+24°')
    expect(weather).toHaveTextContent('Дождливых дней5')
  })

  it('should call less than one rainy day almost none', () => {
    render(<PlaceDetails card={{ ...place, climate: { ...place.climate!, rain_days: 0.4 } }} />)

    expect(screen.getByRole('list', { name: 'Погода в ноябре' })).toHaveTextContent('Дождливых днейпочти нет')
  })

  it('should show the ticket in the trip currency and everything to like and watch out for', () => {
    renderDetails()

    expect(screen.getByRole('link', { name: /Pegasus Airlines/ })).toHaveTextContent(/61\s792 ₸/)
    expect(screen.getByText('Прямой рейс 5,5 ч')).toBeInTheDocument()
    expect(screen.getByText('пляж Клеопатры')).toBeInTheDocument()
    expect(screen.getByText('вечером прохладно')).toBeInTheDocument()
    expect(screen.getByText('От аэропорта Антальи около 2 часов')).toBeInTheDocument()
    expect(screen.getByText('без визы')).toBeInTheDocument()
  })

  it('should show the real photo with its author in the tooltip, not written over it', () => {
    render(<PlaceDetails card={{ ...place, photo: PHOTO }} />)

    expect(document.querySelector(`img[src="${PHOTO.url}"]`)).toHaveAttribute('title', 'Фото: Jane Doe, CC BY-SA 4.0')
    expect(screen.queryByText(/^Фото: Jane Doe/)).toBeNull()
  })

  it('should close with the button and with Escape', async () => {
    const onClose = renderDetails()

    await userEvent.click(screen.getByRole('button', { name: 'Закрыть' }))
    await userEvent.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
