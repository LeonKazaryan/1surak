import type { BriefAnswers, ChatStreamEvent, TripKind } from '@/types/api'
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

/** Per person, for a week; the same team estimates the server uses to pick a price level. */
export const BUDGET_OPTIONS = [
  { level: 1, label: 'Экономно', hint: 'до 70 000 ₽ на человека' },
  { level: 2, label: 'Средне', hint: '70–150 000 ₽ на человека' },
  { level: 3, label: 'Комфорт', hint: 'от 150 000 ₽ на человека' },
  { level: 0, label: 'Не важно', hint: 'покажу разные варианты' },
]

const MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
const MONTHS_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

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
  return `${low}–${high} ${plural(high, ['ночь', 'ночи', 'ночей'])}`
}

export function formatRub(value: number): string {
  return `${value.toLocaleString('ru-RU')} ₽`
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
export function describeAnswers(a: BriefAnswers): string {
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
  if (a.budget_total_rub) parts.push(`бюджет до ${formatRub(a.budget_total_rub)} на всех`)
  else if (a.budget_level !== undefined) {
    const option = BUDGET_OPTIONS.find((o) => o.level === a.budget_level)
    if (option) parts.push(option.level ? `бюджет: ${option.label.toLowerCase()}` : 'бюджет не важен')
  }
  return parts.join(' · ')
}

export function isWidgetEvent(event: ChatStreamEvent | { type?: unknown }): event is ChatWidget {
  return event.type === 'clarify' || event.type === 'destinations'
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
