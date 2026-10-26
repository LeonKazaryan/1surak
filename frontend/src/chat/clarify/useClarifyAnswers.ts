import { useState } from 'react'
import { getDepartureCity, type DepartureCity } from '@/lib/departureCity'
import type { BriefAnswers, ClarifyEvent, ClarifySlot, TripKind } from '@/types/api'
import { prefilledParty, type Party } from './plan'

const PARTY_ADULTS: Record<Party, number> = { solo: 1, couple: 2, kids: 2, group: 3, oneAdult: 1, twoAdults: 2 }

/** The answers being picked on the cards. Starts from what the agent already understood. */
export function useClarifyAnswers({ questions, prefill, currency }: ClarifyEvent) {
  const [kinds, setKinds] = useState<TripKind[]>(prefill.kinds)
  const [month, setMonth] = useState<number | null>(prefill.month)
  const [nights, setNights] = useState<[number, number] | null>(prefill.nights)
  const [party, setParty] = useState<Party | null>(() => prefilledParty(prefill))
  const [adults, setAdults] = useState(prefill.adults ?? 2)
  const [ages, setAges] = useState<(number | null)[]>(() =>
    Array.from({ length: prefill.children ?? 0 }, (_, i) => prefill.children_ages[i] ?? null),
  )
  const [level, setLevelState] = useState<number | null>(prefill.budget_level)
  const [total, setTotalState] = useState<number | null>(prefill.budget_total ?? null)
  const [multiCity, setMultiCity] = useState<boolean | null>(prefill.multi_city)
  // null until the user picks or confirms a city, on its card or on the «Вылет:» chip
  const [origin, setOrigin] = useState<DepartureCity | null>(prefill.origin ?? null)

  const knowsParty = prefill.adults !== null || party !== null
  const knowsKids = party !== 'kids' || ages.length > 0
  const answered: Record<ClarifySlot, boolean> = {
    origin: origin !== null,
    vibe: kinds.length > 0,
    when: month !== null && nights !== null,
    // a default of two adults is not an answer: only what was tapped or said counts
    travelers: knowsParty && knowsKids && ages.every((a) => a !== null),
    route: multiCity !== null,
    budget: total !== null || level !== null,
  }

  const collect = (): BriefAnswers => {
    const answers: BriefAnswers = {}
    const asked = new Set(questions.map((q) => q.slot))
    if (asked.has('vibe') && answered.vibe) answers.kinds = kinds
    if (asked.has('when')) {
      if (month !== null) answers.month = month
      if (nights) [answers.nights_min, answers.nights_max] = nights
    }
    if (asked.has('travelers') && answered.travelers) {
      answers.adults = adults
      answers.children = ages.length
      answers.children_ages = ages as number[]
    }
    if (asked.has('route') && multiCity !== null) answers.multi_city = multiCity
    if (origin) answers.origin = origin.code
    if (asked.has('budget')) {
      if (total !== null) {
        answers.budget_total = total
        answers.budget_currency = currency?.code ?? 'RUB'
      } else if (level !== null) answers.budget_level = level
    }
    return answers
  }

  return {
    kinds,
    setKinds,
    month,
    setMonth,
    nights,
    setNights,
    party,
    adults,
    setAdults,
    ages,
    setAges,
    level,
    total,
    multiCity,
    setMultiCity,
    origin,
    setOrigin,
    /** The city the tickets fly from: the one picked here, or the current guess. */
    home: origin ?? getDepartureCity(),
    choose: (picked: Party) => {
      setParty(picked)
      setAdults(PARTY_ADULTS[picked])
      // with the kids known from the message they stay; otherwise «С детьми» asks how many next
      if (!prefill.children) setAges([])
    },
    setKids: (count: number) => setAges(Array(count).fill(null)),
    setAge: (child: number, age: number) => setAges((prev) => prev.map((a, i) => (i === child ? age : a))),
    // a level and a custom sum exclude each other
    setLevel: (value: number) => {
      setLevelState(value)
      setTotalState(null)
    },
    setTotal: (value: number | null) => {
      setTotalState(value)
      setLevelState(null)
    },
    answered,
    collect,
  }
}

export type ClarifyAnswers = ReturnType<typeof useClarifyAnswers>
