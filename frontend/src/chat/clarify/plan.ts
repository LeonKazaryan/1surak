import type { ClarifyEvent, ClarifyPrefill, ClarifySlot } from '@/types/api'
import { BUDGET_OPTIONS, KIND_OPTIONS, MONTHS, nightsLabel, plural } from '../widgets'

/** One question of the agent: which parts of it are still unknown, so nothing is asked twice. */
export interface CardPlan {
  slot: ClarifySlot
  hint?: string | null
  /** Short name of the question, for the chat chip. */
  label: string
  askMonth: boolean
  askNights: boolean
  askCounts: boolean
}

export function planCards({ questions, prefill }: ClarifyEvent): CardPlan[] {
  return questions.map((q) => {
    const base = { slot: q.slot, hint: q.hint, askMonth: false, askNights: false, askCounts: false }
    switch (q.slot) {
      case 'vibe':
        return { ...base, label: 'Отдых' }
      case 'when': {
        const knowsMonth = prefill.month !== null
        const knowsNights = prefill.nights !== null
        return { ...base, label: 'Даты', askMonth: !knowsMonth || knowsNights, askNights: !knowsNights || knowsMonth }
      }
      case 'travelers':
        return { ...base, label: 'Кто едет', askCounts: prefill.adults === null }
      case 'budget':
        return { ...base, label: 'Бюджет' }
    }
  })
}

/** Who travels, picked with one tap; the ones with children know the kids from the message already. */
export type Party = 'solo' | 'couple' | 'kids' | 'group' | 'oneAdult' | 'twoAdults'

export function partyOptions(prefill: ClarifyPrefill): Party[] {
  if (prefill.children) return ['oneAdult', 'twoAdults']
  return prefill.children === 0 ? ['solo', 'couple', 'group'] : ['solo', 'couple', 'kids', 'group']
}

export type StepKind = 'vibe' | 'month' | 'nights' | 'party' | 'kids' | 'adults' | 'age' | 'budget'

/** One tap of the deck. A question can take a few: «С детьми» adds «Сколько детей?» and an age per child. */
export interface Step {
  key: string
  kind: StepKind
  slot: ClarifySlot
  title: string
  hint?: string | null
  child?: number
}

export interface StepState {
  party: Party | null
  ages: (number | null)[]
}

const ORDINALS = ['первому', 'второму', 'третьему', 'четвёртому', 'пятому']

function ageTitle(child: number, kids: number): string {
  return kids > 1 ? `Сколько лет ${ORDINALS[child] ?? `${child + 1}-му`} ребёнку?` : 'Сколько лет ребёнку?'
}

export function buildSteps(event: ClarifyEvent, state: StepState): Step[] {
  const { prefill } = event
  const steps: Step[] = []
  for (const plan of planCards(event)) {
    const first = steps.length
    const add = (step: Omit<Step, 'slot' | 'hint'>) =>
      steps.push({ ...step, slot: plan.slot, hint: steps.length === first ? plan.hint : null })
    switch (plan.slot) {
      case 'vibe':
        add({ key: 'vibe', kind: 'vibe', title: 'Какой отдых хочется?' })
        break
      case 'when':
        if (plan.askMonth) add({ key: 'month', kind: 'month', title: 'В каком месяце?' })
        if (plan.askNights) add({ key: 'nights', kind: 'nights', title: 'На сколько ночей?' })
        break
      case 'travelers':
        if (plan.askCounts) {
          add({ key: 'party', kind: 'party', title: 'Кто едет?' })
          if (state.party === 'kids') add({ key: 'kids', kind: 'kids', title: 'Сколько детей?' })
          if (state.party === 'group') add({ key: 'adults', kind: 'adults', title: 'Сколько взрослых?' })
        }
        state.ages.forEach((_, child) => {
          if (prefill.children_ages[child] === undefined) {
            add({ key: `age-${child}`, kind: 'age', child, title: ageTitle(child, state.ages.length) })
          }
        })
        break
      case 'budget':
        add({ key: 'budget', kind: 'budget', title: 'Какой бюджет?' })
        break
    }
  }
  return steps
}

/** How far the plane has flown at this step: whole questions done plus the share of the current one. */
export function progressAt(steps: Step[], index: number, slots: ClarifySlot[]): number {
  const step = steps[index]
  if (!step || !slots.length) return 0
  const ofSlot = steps.filter((s) => s.slot === step.slot)
  return (slots.indexOf(step.slot) + ofSlot.indexOf(step) / ofSlot.length) / slots.length
}

/** What the agent already understood from the message, shown above the cards. */
export function knownFacts(prefill: ClarifyPrefill): string[] {
  const facts: string[] = []
  if (prefill.kinds.length) {
    const labels = prefill.kinds.map((k) => KIND_OPTIONS.find((o) => o.kind === k)?.label ?? k)
    facts.push(labels.join(', '))
  }
  if (prefill.month) facts.push(MONTHS[prefill.month - 1].replace(/^./, (c) => c.toUpperCase()))
  if (prefill.nights) facts.push(nightsLabel(prefill.nights))
  if (prefill.adults) facts.push(`${prefill.adults} ${plural(prefill.adults, ['взрослый', 'взрослых', 'взрослых'])}`)
  if (prefill.children) facts.push(`${prefill.children} ${plural(prefill.children, ['ребёнок', 'ребёнка', 'детей'])}`)
  const budget = BUDGET_OPTIONS.find((o) => o.level === prefill.budget_level)
  if (budget) facts.push(budget.level ? `Бюджет: ${budget.label.toLowerCase()}` : 'Бюджет не важен')
  return facts
}
