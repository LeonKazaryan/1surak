import type { ClarifyEvent, ClarifyPrefill, ClarifySlot } from '@/types/api'
import { BUDGET_OPTIONS, KIND_OPTIONS, MONTHS, nightsLabel, plural } from '../widgets'

/** One card of the deck: which parts of its question are still unknown, so nothing is asked twice. */
export interface CardPlan {
  slot: ClarifySlot
  title: string
  hint?: string | null
  /** Short name on the progress trail. */
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
        return { ...base, title: 'Какой отдых хочется?', label: 'Отдых', hint: q.hint || 'Можно выбрать несколько' }
      case 'when': {
        const knowsMonth = prefill.month !== null
        const knowsNights = prefill.nights !== null
        const askMonth = !knowsMonth || knowsNights
        const askNights = !knowsNights || knowsMonth
        const title = askMonth && askNights ? 'Когда и на сколько?' : askMonth ? 'В каком месяце?' : 'На сколько ночей?'
        return { ...base, title, label: 'Даты', askMonth, askNights }
      }
      case 'travelers': {
        const askCounts = prefill.adults === null
        const kids = prefill.children ?? 0
        const title = askCounts ? 'Кто едет?' : kids > 1 ? 'Сколько лет детям?' : 'Сколько лет ребёнку?'
        return { ...base, title, label: 'Кто едет', askCounts }
      }
      case 'budget':
        return { ...base, title: 'Какой бюджет?', label: 'Бюджет' }
    }
  })
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
