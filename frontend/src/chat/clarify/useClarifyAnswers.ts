import { useState } from 'react'
import type { BriefAnswers, ClarifyEvent, ClarifySlot, TripKind } from '@/types/api'

/** The answers being picked on the cards. Starts from what the agent already understood. */
export function useClarifyAnswers({ questions, prefill }: ClarifyEvent) {
  const [kinds, setKinds] = useState<TripKind[]>(prefill.kinds)
  const [month, setMonth] = useState<number | null>(prefill.month)
  const [nights, setNights] = useState<[number, number] | null>(prefill.nights)
  const [adults, setAdults] = useState(prefill.adults ?? 2)
  const [ages, setAges] = useState<(number | null)[]>(() =>
    Array.from({ length: prefill.children ?? 0 }, (_, i) => prefill.children_ages[i] ?? null),
  )
  const [level, setLevelState] = useState<number | null>(prefill.budget_level)
  const [total, setTotalState] = useState<number | null>(null)

  const answered: Record<ClarifySlot, boolean> = {
    vibe: kinds.length > 0,
    when: month !== null && nights !== null,
    travelers: adults >= 1 && ages.every((a) => a !== null),
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
    if (asked.has('budget')) {
      if (total !== null) answers.budget_total_rub = total
      else if (level !== null) answers.budget_level = level
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
    adults,
    setAdults,
    ages,
    setAges,
    level,
    total,
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
