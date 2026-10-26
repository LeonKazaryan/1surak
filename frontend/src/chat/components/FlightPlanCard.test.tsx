import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { FlightPlanEvent, RouteFlight } from '@/types/api'
import { FlightPlanCards } from './FlightPlanCard'

const ticket = (price: number, link: string, departure: string): RouteFlight => ({
  price_rub: price,
  airline: 'TK',
  airline_name: 'Turkish Airlines',
  logo: '',
  flight_number: 'TK 1',
  transfers: 0,
  hours: 3,
  departure,
  link,
  direct_available: true,
})

const WIDGET: FlightPlanEvent = {
  type: 'flight_plan',
  from: 'Москва',
  plans: [
    {
      id: 'IST+BJV',
      name: 'Москва → Стамбул → Бодрум',
      best: true,
      legs: [
        { from: 'Москва', to: 'Стамбул', mode: 'flight', km: 1756, ticket: ticket(10_000, 'https://www.aviasales.ru/a', '2026-12-05 08:00') },
        {
          from: 'Стамбул',
          to: 'Бодрум',
          mode: 'flight',
          km: 500,
          ticket: ticket(9_000, 'https://www.aviasales.ru/b', '2026-12-08 09:00'),
          via: {
            via: 'Измир',
            price_rub: 5_000,
            hours: 6,
            layover_hours: 3,
            separate_tickets: true,
            saves_rub: 4_000,
            tickets: [ticket(3_000, 'https://www.aviasales.ru/c', '2026-12-08 07:00'), ticket(2_000, 'https://www.aviasales.ru/d', '2026-12-08 13:00')],
          },
        },
        { from: 'Бодрум', to: 'Суздаль', mode: 'none', km: null, estimate: 'нет ни рейса, ни поезда' },
      ],
      total_rub: 19_000,
      total_complete: false,
      total_with_connections_rub: 15_000,
      dates_chained: true,
      travel_hours: 6,
    },
  ],
}

describe('FlightPlanCards', () => {
  it('should link every ticket to Aviasales', () => {
    render(<FlightPlanCards widget={WIDGET} />)

    const links = screen.getAllByRole('link').map((a) => a.getAttribute('href'))
    expect(links).toEqual(['https://www.aviasales.ru/a', 'https://www.aviasales.ru/b', 'https://www.aviasales.ru/c', 'https://www.aviasales.ru/d'])
  })

  it('should show the total, the cheaper hub and whether the dates chain', () => {
    render(<FlightPlanCards widget={WIDGET} />)

    expect(screen.getByText('Москва → Стамбул → Бодрум')).toBeInTheDocument()
    expect(screen.getByText(/от 19\s000 ₽/)).toBeInTheDocument()
    expect(screen.getByText('Дешевле через Измир')).toBeInTheDocument()
    expect(screen.getByText(/15\s000 ₽/)).toBeInTheDocument()
    expect(screen.getByText(/Даты состыкованы/)).toBeInTheDocument()
    expect(screen.getByText('нет ни рейса, ни поезда')).toBeInTheDocument()
  })
})
