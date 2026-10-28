import type { Photo, TripPassport } from '@/types/api'
import type { WorkspaceChatMessage } from '../types'

/** A field of the trip someone can change from the header. */
export type PassportField = 'destination' | 'when' | 'travelers' | 'budget' | 'origin'

export type ChipKind = PassportField | 'kinds' | 'multi' | 'visa' | 'land' | 'wish'

export interface PassportChip {
  key: string
  kind: ChipKind
  text: string
  field?: PassportField
  ghost?: boolean
}

const capital = (text: string) => text.replace(/^./, (c) => c.toUpperCase())

/** The trip's chips in reading order; the core fields not known yet are ghosts that ask for them. */
export function passportChips(p: TripPassport | null | undefined, ghosts = true): PassportChip[] {
  const chips: PassportChip[] = []
  const core: [PassportField, string | null | undefined, string][] = [
    ['when', p?.when, 'Когда?'],
    ['travelers', p?.travelers, 'Кто едет?'],
    ['budget', p?.budget, 'Бюджет?'],
  ]
  for (const [field, value, ask] of core) {
    if (value) chips.push({ key: `${field}:${value}`, kind: field, text: value, field })
    else if (ghosts) chips.push({ key: `${field}:?`, kind: field, text: ask, field, ghost: true })
  }
  if (p?.origin) chips.push({ key: `origin:${p.origin.code}`, kind: 'origin', text: capital(p.origin.from), field: 'origin' })
  if (!p?.destination && p?.kinds.length) {
    chips.push({ key: 'kinds', kind: 'kinds', text: capital(p.kinds.map((k) => k.label).join(', ')) })
  }
  if (p?.multi_city) chips.push({ key: 'multi', kind: 'multi', text: p.multi_country ? 'Несколько стран' : 'Несколько городов' })
  if (p?.visa_free_only) chips.push({ key: 'visa', kind: 'visa', text: 'Без визы' })
  if (p?.by_land) chips.push({ key: 'land', kind: 'land', text: 'Поездом' })
  for (const wish of p?.wishes ?? []) chips.push({ key: `wish:${wish}`, kind: 'wish', text: wish })
  return chips
}

/** What the composer starts with when a chip is tapped: the user finishes the sentence. */
export const EDIT_PROMPTS: Record<PassportField, string> = {
  destination: 'Хочу поехать в ',
  when: 'Поменяй даты: ',
  travelers: 'Едем ',
  budget: 'Бюджет: ',
  origin: 'Вылет из ',
}

export type TripStage = 'idea' | 'options' | 'plan' | 'booked'
export const STAGES: { stage: TripStage; label: string }[] = [
  { stage: 'idea', label: 'Идея' },
  { stage: 'options', label: 'Варианты' },
  { stage: 'plan', label: 'План' },
  { stage: 'booked', label: 'Бронь' },
]

/** How far the trip has come: the latest thing the agent showed. */
export function stageOf(messages: WorkspaceChatMessage[]): TripStage {
  const kinds = new Set(messages.map((m) => m.widget?.type))
  if (kinds.has('booking')) return 'booked'
  if (kinds.has('trip_plan')) return 'plan'
  if (kinds.has('destinations') || kinds.has('flight_plan')) return 'options'
  return 'idea'
}

/** The cover's photo: the place the user named, else the first card or stop the agent showed. */
export function coverPhoto(passport: TripPassport | null | undefined, messages: WorkspaceChatMessage[]): Photo | null {
  if (passport?.destination?.photo) return passport.destination.photo
  for (const m of [...messages].reverse()) {
    const w = m.widget
    if (w?.type === 'trip_plan') {
      const photo = w.stops.find((s) => s.photo)?.photo
      if (photo) return photo
    }
    if (w?.type === 'destinations') {
      for (const card of w.cards) {
        const photo = card.type === 'route' ? card.stops.find((s) => s.photo)?.photo : card.photo
        if (photo) return photo
      }
    }
  }
  return null
}
