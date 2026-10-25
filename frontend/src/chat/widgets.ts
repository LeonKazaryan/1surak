import { createContext } from 'react'
import type { BriefAnswers, ChatStreamEvent, Currency, TripKind } from '@/types/api'
import type { ChatWidget } from './types'

export const KIND_OPTIONS: { kind: TripKind; label: string }[] = [
  { kind: 'sea', label: 'Море и пляж' },
  { kind: 'mountains', label: 'Горы' },
  { kind: 'city', label: 'Города и экскурсии' },
  { kind: 'nature', label: 'Природа' },
  { kind: 'ski', label: 'Горные лыжи' },
]

export const NIGHT_OPTIONS: [number, number][] = [
  [2, 4],
  [5, 7],
  [8, 10],
  [11, 14],
  [15, 20],
]

export const RUB: Currency = { code: 'RUB', sign: '₽', glyph: '₽', per_rub: 1 }
/** Cards set it from their event: older saved messages have none and stay in roubles. */
export const CurrencyContext = createContext<Currency>(RUB)

const PRICE_GAP = /(\d) (?=\d{3}\b|₽|₸|\$|€|Br\b|сум|сом)/g

/** «72 504 ₸» as the model typed it, with no-break spaces, so a line never ends inside a price. */
export function keepPricesTogether(text: string): string {
  return text.replace(PRICE_GAP, '$1\u00a0')
}

export function formatMoney(rub: number, currency: Currency = RUB): string {
  return `${Math.round(rub * currency.per_rub).toLocaleString('ru-RU')} ${currency.sign}`
}

/** 389 329 → 390 000: a converted budget reads like a sum someone would say. */
function roundSum(value: number): number {
  const step = 10 ** Math.max(0, Math.floor(Math.log10(value)) - 1)
  return Math.round(value / step) * step
}

/** Per person, for a week, in roubles: the same team estimates the server uses to pick a price level. */
export const BUDGET_OPTIONS = [
  { level: 1, label: 'Экономно', upTo: 70_000 },
  { level: 2, label: 'Средне', upTo: 150_000 },
  { level: 3, label: 'Комфорт', from: 150_000 },
  { level: 0, label: 'Не важно' },
]

export function budgetHint(level: number, currency: Currency = RUB): string {
  const option = BUDGET_OPTIONS.find((o) => o.level === level)
  const rub = option?.upTo ?? option?.from
  if (!rub) return 'покажу разные варианты'
  const sum = `${roundSum(rub * currency.per_rub).toLocaleString('ru-RU')} ${currency.sign}`
  return `${option?.upTo ? 'до' : 'от'} ${sum} на человека`
}

export const MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
export const MONTHS_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

export interface MonthOption {
  month: number
  label: string
  year: number
}

/** The next twelve months starting with the current one: nobody plans a trip into the past. */
export function upcomingMonths(today: Date = new Date()): MonthOption[] {
  return Array.from({ length: 12 }, (_, i) => {
    const date = new Date(today.getFullYear(), today.getMonth() + i, 1)
    return { month: date.getMonth() + 1, label: MONTHS_SHORT[date.getMonth()], year: date.getFullYear() }
  })
}

/** Russian plural: (1 ночь, 2 ночи, 5 ночей). */
export function plural(n: number, forms: [string, string, string]): string {
  const tail = n % 100
  if (tail >= 11 && tail <= 14) return forms[2]
  if (n % 10 === 1) return forms[0]
  return n % 10 >= 2 && n % 10 <= 4 ? forms[1] : forms[2]
}

export function nightsLabel([low, high]: [number, number]): string {
  return `${low === high ? low : `${low}–${high}`} ${plural(high, ['ночь', 'ночи', 'ночей'])}`
}

function travelersText(a: BriefAnswers): string | null {
  if (!a.adults) return null
  let text = `${a.adults} ${plural(a.adults, ['взрослый', 'взрослых', 'взрослых'])}`
  const kids = a.children ?? 0
  if (kids) {
    text += ` + ${kids} ${plural(kids, ['ребёнок', 'ребёнка', 'детей'])}`
    const ages = a.children_ages ?? []
    if (ages.length) {
      const last = ages[ages.length - 1]
      const head = ages.slice(0, -1).join(', ')
      text += ` (${head ? `${head} и ` : ''}${last} ${plural(last, ['год', 'года', 'лет'])})`
    }
  }
  return text
}

/** The answers as the user's own chat message, so the conversation reads naturally and the model sees it. */
export function describeAnswers(a: BriefAnswers, currency: Currency = RUB): string {
  const parts: string[] = []
  if (a.kinds?.length) {
    const labels = a.kinds.map((k) => KIND_OPTIONS.find((o) => o.kind === k)?.label ?? k)
    parts.push(labels.join(', ').toLowerCase().replace(/^./, (c) => c.toUpperCase()))
  }
  const when = [
    a.month ? MONTHS[a.month - 1] : null,
    a.nights_min && a.nights_max ? nightsLabel([a.nights_min, a.nights_max]) : null,
  ].filter(Boolean)
  if (when.length) parts.push(when.join(', '))
  const travelers = travelersText(a)
  if (travelers) parts.push(travelers)
  if (a.budget_total) parts.push(`бюджет до ${a.budget_total.toLocaleString('ru-RU')} ${currency.sign} на всех`)
  else if (a.budget_level !== undefined) {
    const option = BUDGET_OPTIONS.find((o) => o.level === a.budget_level)
    if (option) parts.push(option.level ? `бюджет: ${option.label.toLowerCase()}` : 'бюджет не важен')
  }
  if (a.multi_city !== undefined) parts.push(a.multi_city ? 'несколько городов' : 'один город')
  return parts.join(' · ')
}

export function isWidgetEvent(event: ChatStreamEvent | { type?: unknown }): event is ChatWidget {
  return event.type === 'clarify' || event.type === 'destinations' || event.type === 'trip_plan' || event.type === 'booking'
}

/** The cards of a saved assistant message, rebuilt from its persisted stream events. */
export function widgetFromTrace(events: unknown[]): ChatWidget | undefined {
  return events
    .filter((e): e is ChatWidget => typeof e === 'object' && e !== null && isWidgetEvent(e as { type?: unknown }))
    .at(-1)
}

export function flagEmoji(countryCode: string): string {
  if (!/^[A-Z]{2}$/.test(countryCode)) return ''
  return String.fromCodePoint(...[...countryCode].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65))
}
