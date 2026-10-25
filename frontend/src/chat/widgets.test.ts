import { describe, expect, it } from 'vitest'
import { budgetHint, describeAnswers, flagEmoji, formatMoney, plural, upcomingMonths, widgetFromTrace } from './widgets'

const KZT = { code: 'KZT', sign: '₸', glyph: '₸', per_rub: 5.561828 }

describe('widgets', () => {
  it('should pick Russian plural forms', () => {
    const forms: [string, string, string] = ['ночь', 'ночи', 'ночей']
    expect([1, 2, 5, 11, 21, 22, 112].map((n) => plural(n, forms))).toEqual([
      'ночь',
      'ночи',
      'ночей',
      'ночей',
      'ночь',
      'ночи',
      'ночей',
    ])
  })

  it('should list the next twelve months from the current one, across the new year', () => {
    const months = upcomingMonths(new Date(2026, 9, 25))

    expect(months).toHaveLength(12)
    expect(months[0]).toEqual({ month: 10, label: 'окт', year: 2026 })
    expect(months[3]).toEqual({ month: 1, label: 'янв', year: 2027 })
  })

  it('should show roubles in the user currency', () => {
    expect(formatMoney(7707).replace(/\s/g, ' ')).toBe('7 707 ₽')
    expect(formatMoney(7707, KZT).replace(/\s/g, ' ')).toBe('42 865 ₸')
  })

  it('should give the budget levels as round sums in the user currency', () => {
    expect(budgetHint(1).replace(/\s/g, ' ')).toBe('до 70 000 ₽ на человека')
    expect(budgetHint(1, KZT).replace(/\s/g, ' ')).toBe('до 390 000 ₸ на человека')
    expect(budgetHint(3, KZT).replace(/\s/g, ' ')).toBe('от 830 000 ₸ на человека')
    expect(budgetHint(0, KZT)).toBe('покажу разные варианты')
  })

  it('should write a budget in tenge into the user message', () => {
    expect(describeAnswers({ budget_total: 500000, budget_currency: 'KZT' }, KZT).replace(/\s/g, ' ')).toBe(
      'бюджет до 500 000 ₸ на всех',
    )
  })

  it('should turn card answers into a natural message', () => {
    expect(
      describeAnswers({
        kinds: ['sea', 'mountains'],
        month: 11,
        nights_min: 5,
        nights_max: 7,
        adults: 2,
        children: 2,
        children_ages: [3, 7],
        budget_total: 300000,
        budget_currency: 'RUB',
      }).replace(/\s/g, ' '), // thousands are split by a no-break space
    ).toBe('Море и пляж, горы · ноябрь, 5–7 ночей · 2 взрослых + 2 ребёнка (3 и 7 лет) · бюджет до 300 000 ₽ на всех')
    expect(describeAnswers({ budget_level: 0 })).toBe('бюджет не важен')
    expect(describeAnswers({ multi_city: true })).toBe('несколько городов')
  })

  it('should take the last widget from a saved trace and ignore other events', () => {
    const destinations = { type: 'destinations', summary: [], cards: [] }
    const trace = [{ type: 'tool_start', name: 'x' }, { type: 'clarify', questions: [], prefill: {} }, destinations, null]

    expect(widgetFromTrace(trace)).toBe(destinations)
    expect(widgetFromTrace([{ type: 'tool_end' }])).toBeUndefined()
  })

  it('should draw a flag from a country code', () => {
    expect(flagEmoji('TR')).toBe('🇹🇷')
    expect(flagEmoji('tr')).toBe('')
  })
})
