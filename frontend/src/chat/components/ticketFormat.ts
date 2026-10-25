import type { DestinationCard, FlightTicket } from '@/types/api'
import { plural } from '../widgets'

const MONTHS_GEN = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

export function hours(value: number): string {
  return `${value.toLocaleString('ru-RU')} ч`
}

export function temp(value: number): string {
  return `${value > 0 ? '+' : ''}${value}°`
}

export function shortDate(departure: string): string {
  const [, month, day] = departure.slice(0, 10).split('-').map(Number)
  return month ? `${day} ${MONTHS_GEN[month - 1]}` : ''
}

export function travelText(card: DestinationCard): string | null {
  if (card.flight_hours) return `${hours(card.flight_hours)} · ${card.direct ? 'прямой' : 'с пересадкой'}`
  if (card.train_hours) return `поезд ${hours(card.train_hours)}`
  return null
}

export function stopsText(t: FlightTicket): string {
  return t.transfers === 0 ? 'прямой' : `${t.transfers} ${plural(t.transfers, ['пересадка', 'пересадки', 'пересадок'])}`
}
