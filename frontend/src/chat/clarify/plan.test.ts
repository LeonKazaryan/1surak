import { describe, expect, it } from 'vitest'
import type { ClarifyEvent, ClarifyPrefill } from '@/types/api'
import { knownFacts, planCards } from './plan'

const EMPTY: ClarifyPrefill = { kinds: [], month: null, nights: null, adults: null, children: null, children_ages: [], budget_level: null }

function event(slots: ClarifyEvent['questions'][number]['slot'][], prefill: Partial<ClarifyPrefill> = {}): ClarifyEvent {
  return { type: 'clarify', questions: slots.map((slot) => ({ slot, title: 'x' })), prefill: { ...EMPTY, ...prefill } }
}

describe('planCards', () => {
  it('should not ask again for the month the user already named', () => {
    const [when] = planCards(event(['when'], { month: 11 }))

    expect(when).toMatchObject({ title: 'На сколько ночей?', askMonth: false, askNights: true })
  })

  it('should ask for both parts of the dates when nothing is known', () => {
    const [when] = planCards(event(['when']))

    expect(when).toMatchObject({ title: 'Когда и на сколько?', askMonth: true, askNights: true })
  })

  it('should only ask the age when the party is known but a child has none', () => {
    const [travelers] = planCards(event(['travelers'], { adults: 2, children: 2 }))

    expect(travelers).toMatchObject({ title: 'Сколько лет детям?', askCounts: false })
    expect(planCards(event(['travelers'], { children: 1 }))[0]).toMatchObject({ title: 'Кто едет?', askCounts: true })
  })
})

describe('knownFacts', () => {
  it('should list what the agent understood in short phrases', () => {
    expect(knownFacts({ ...EMPTY, kinds: ['sea', 'mountains'], month: 11, nights: [7, 7], children: 1, budget_level: 1 })).toEqual([
      'Море и пляж, Горы',
      'Ноябрь',
      '7 ночей',
      '1 ребёнок',
      'Бюджет: экономно',
    ])
  })
})
