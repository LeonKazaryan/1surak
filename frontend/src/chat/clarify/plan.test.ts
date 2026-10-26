import { describe, expect, it } from 'vitest'
import type { ClarifyEvent, ClarifyPrefill, ClarifySlot } from '@/types/api'
import { buildSteps, knownFacts, partyOptions, prefilledParty, progressAt, type StepState } from './plan'

const EMPTY: ClarifyPrefill = { kinds: [], month: null, nights: null, adults: null, children: null, children_ages: [], budget_level: null, multi_city: null }
const NOTHING_PICKED: StepState = { party: null, ages: [] }

function event(slots: ClarifySlot[], prefill: Partial<ClarifyPrefill> = {}): ClarifyEvent {
  return { type: 'clarify', questions: slots.map((slot) => ({ slot, title: 'x', hint: `про ${slot}` })), prefill: { ...EMPTY, ...prefill } }
}

const keys = (e: ClarifyEvent, state: StepState = NOTHING_PICKED) => buildSteps(e, state).map((s) => s.key)

describe('buildSteps', () => {
  it('should ask where the trip starts first, when the city was only a guess', () => {
    expect(keys(event(['origin', 'when']))).toEqual(['origin', 'month', 'nights'])
  })

  it('should show the month the user named too, so it is confirmed in one tap', () => {
    expect(keys(event(['when'], { month: 11 }))).toEqual(['month', 'nights'])
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

  it('should confirm the party from the message and ask only the ages it did not say', () => {
    const e = event(['travelers'], { adults: 2, children: 2, children_ages: [7] })
    const steps = buildSteps(e, { party: prefilledParty(e.prefill), ages: [7, null] })

    expect(steps.map((s) => [s.key, s.title])).toEqual([
      ['party', 'Кто едет?'],
      ['age-1', 'Сколько лет второму ребёнку?'],
    ])
  })

  it('should preselect the party the message described', () => {
    expect(prefilledParty({ ...EMPTY, adults: 2, children: 0 })).toBe('couple')
    expect(prefilledParty({ ...EMPTY, adults: 1 })).toBe('solo')
    expect(prefilledParty({ ...EMPTY, adults: 2, children: 1 })).toBe('twoAdults')
    expect(prefilledParty({ ...EMPTY, adults: 4 })).toBe('group')
    expect(prefilledParty(EMPTY)).toBeNull()
  })

  it('should move the plane forward with every tap, never back', () => {
    const slots: ClarifySlot[] = ['travelers', 'budget']
    const steps = buildSteps(event(slots), { party: 'kids', ages: [null] })

    expect(steps.map((_, i) => progressAt(steps, i, slots))).toEqual([0, 1 / 6, 1 / 3, 0.5])
  })
})

describe('route step', () => {
  it('should ask about a route, and drop the question once «С детьми» or skiing is picked in the deck', () => {
    const e = event(['vibe', 'travelers', 'route', 'budget'])

    expect(keys(e)).toEqual(['vibe', 'party', 'route', 'budget'])
    expect(keys(e, { party: 'kids', ages: [null] })).not.toContain('route')
    expect(keys(e, { party: 'couple', ages: [], kinds: ['ski'] })).not.toContain('route')
    expect(keys(e, { party: 'couple', ages: [], kinds: ['city'] })).toContain('route')
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
