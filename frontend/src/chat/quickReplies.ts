import type { DestinationsCard, TripPassport } from '@/types/api'
import type { WorkspaceChatMessage } from './types'

const NO_VISA = new Set(['none', 'visa_free'])

function needsVisa(card: DestinationsCard): boolean {
  const rules = card.type === 'route' ? card.stops.map((s) => s.visa_info?.rule) : [card.visa_info?.rule]
  return rules.some((rule) => rule !== undefined && !NO_VISA.has(rule))
}

/** The next steps that make sense after the latest answer: what the user would likely say anyway. */
export function quickReplies(last: WorkspaceChatMessage | undefined, passport: TripPassport | null | undefined): string[] {
  const widget = last?.role === 'assistant' ? last.widget : undefined
  if (widget?.type === 'destinations') {
    const visa = widget.cards.some(needsVisa) && !passport?.visa_free_only
    return [
      'Покажи подешевле',
      ...(visa ? ['Только без визы'] : []),
      passport?.multi_city ? 'Лучше один город' : 'Хочу несколько городов',
      'Другие варианты',
    ]
  }
  if (widget?.type === 'trip_plan') return ['Сделай подешевле', 'Другой отель', 'Больше музеев и прогулок', 'Что взять с собой?']
  if (widget?.type === 'flight_plan') return ['Найди дешевле', 'Только прямые рейсы']
  return []
}
