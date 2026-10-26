import type { TripPlanEvent } from '@/types/api'
import { plural } from '../widgets'

const MONTHS_OF = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
const WEEKDAYS = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']
const WEEKDAYS_SHORT = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']

/** «2026-11-06» as a calendar day, with no time zone shift. */
function parts(iso: string): { year: number; month: number; day: number; weekday: number } {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
  return { year, month, day, weekday: new Date(Date.UTC(year, month - 1, day)).getUTCDay() }
}

export function dayText(iso: string): string {
  const { month, day } = parts(iso)
  return `${day} ${MONTHS_OF[month - 1]}`
}

/** «6–13 ноября», or «28 октября – 4 ноября» across two months. */
export function spanText(from: string, to: string): string {
  const a = parts(from)
  const b = parts(to)
  return a.month === b.month ? `${a.day}–${b.day} ${MONTHS_OF[b.month - 1]}` : `${dayText(from)} – ${dayText(to)}`
}

export function nightsText(nights: number): string {
  return `${nights} ${plural(nights, ['ночь', 'ночи', 'ночей'])}`
}

export function dayChip(iso: string): { weekday: string; day: number; label: string } {
  const { day, weekday } = parts(iso)
  return { weekday: WEEKDAYS_SHORT[weekday], day, label: `${WEEKDAYS[weekday]}, ${dayText(iso)}` }
}

/** «2 взрослых, ребёнок 5 лет» or «2 взрослых, дети 3 и 8 лет». */
export function partyText({ adults, children_ages: ages }: TripPlanEvent['party']): string {
  const grown = `${adults} ${plural(adults, ['взрослый', 'взрослых', 'взрослых'])}`
  if (!ages.length) return grown
  const last = ages[ages.length - 1]
  const years = `${last} ${plural(last, ['год', 'года', 'лет'])}`
  if (ages.length === 1) return `${grown}, ребёнок ${years}`
  return `${grown}, дети ${ages.slice(0, -1).join(', ')} и ${years}`
}

/** «09:40» from a local «2026-11-06T09:40». */
export function clock(local: string | null): string | null {
  return local ? local.slice(11, 16) : null
}

export interface BillLine {
  label: string
  note: string
  rub: number
}

export function billLines(plan: TripPlanEvent): BillLine[] {
  const { costs, party } = plan
  const guests = party.adults + party.children_ages.length
  const lines: BillLine[] = []
  if (costs.flights || plan.legs.some((l) => l.mode === 'flight')) {
    const note = costs.flights_complete
      ? `${guests} ${plural(guests, ['пассажир', 'пассажира', 'пассажиров'])}, все перелёты`
      : 'без перелётов, где билетов пока нет'
    lines.push({ label: 'Перелёты', note, rub: costs.flights })
  }
  for (const stop of plan.stops) {
    lines.push({
      label: `Отель «${stop.hotel.name}»`,
      // an estimated meal plan is not promised on the bill either
      note: stop.hotel.terms_known === false ? nightsText(stop.hotel.nights) : `${nightsText(stop.hotel.nights)}, ${stop.hotel.meal_label}`,
      rub: stop.hotel.total_rub,
    })
  }
  if (costs.transfers) lines.push({ label: 'Трансферы', note: 'из аэропорта и обратно', rub: costs.transfers })
  if (costs.ground) lines.push({ label: 'Переезды по земле', note: 'оценка по расстоянию', rub: costs.ground })
  return lines
}
