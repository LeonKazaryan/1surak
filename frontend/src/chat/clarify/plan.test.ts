import { describe, expect, it } from 'vitest'
import type { ClarifyEvent, ClarifyPrefill, ClarifySlot } from '@/types/api'
import { buildSteps, knownFacts, partyOptions, progressAt, type StepState } from './plan'

const EMPTY: ClarifyPrefill = { kinds: [], month: null, nights: null, adults: null, children: null, children_ages: [], budget_level: null }
const NOTHING_PICKED: StepState = { party: null, ages: [] }

function event(slots: ClarifySlot[], prefill: Partial<ClarifyPrefill> = {}): ClarifyEvent {
  return { type: 'clarify', questions: slots.map((slot) => ({ slot, title: 'x', hint: `про ${slot}` })), prefill: { ...EMPTY, ...prefill } }
}

const keys = (e: ClarifyEvent, state: StepState = NOTHING_PICKED) => buildSteps(e, state).map((s) => s.key)

describe('buildSteps', () => {
  it('should not ask again for the month the user already named', () => {
    expect(keys(event(['when'], { month: 11 }))).toEqual(['nights'])
    expect(keys(event(['when']))).toEqual(['month', 'nights'])
  })

  it('should put the agent hint on the first tap of a question only', () => {
    expect(buildSteps(event(['when']), NOTHING_PICKED).map((s) => s.hint)).toEqual(['про when', null])
  })

  it('should grow the travellers question with the taps: kids, then an age per child', () => {
    const e = event(['travelers', 'budget'])

    expect(keys(e)).toEqual(['party', 'budget'])
    expect(keys(e, { party: 'kids', ages: [] })).toEqual(['party', 'kids', 'budget'])
    expect(keys(e, { party: 'kids', ages: [null, null] })).toEqual(['party', 'kids', 'age-0', 'age-1', 'budget'])
    expect(keys(e, { party: 'group', ages: [] })).toEqual(['party', 'adults', 'budget'])
  })

  it('should only ask the ages when the party is known from the message', () => {
    const steps = buildSteps(event(['travelers'], { adults: 2, children: 2, children_ages: [7] }), { party: null, ages: [7, null] })

    expect(steps.map((s) => [s.key, s.title])).toEqual([['age-1', 'Сколько лет второму ребёнку?']])
  })

  it('should move the plane forward with every tap, never back', () => {
    const slots: ClarifySlot[] = ['travelers', 'budget']
    const steps = buildSteps(event(slots), { party: 'kids', ages: [null] })

    expect(steps.map((_, i) => progressAt(steps, i, slots))).toEqual([0, 1 / 6, 1 / 3, 0.5])
  })
})

describe('partyOptions', () => {
  it('should offer only the adults when the kids are already known', () => {
    expect(partyOptions({ ...EMPTY, children: 1 })).toEqual(['oneAdult', 'twoAdults'])
    expect(partyOptions({ ...EMPTY, children: 0 })).toEqual(['solo', 'couple', 'group'])
    expect(partyOptions(EMPTY)).toEqual(['solo', 'couple', 'kids', 'group'])
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
