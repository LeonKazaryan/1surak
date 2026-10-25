import { describe, expect, it } from 'vitest'
import { describeAnswers, flagEmoji, plural, upcomingMonths, widgetFromTrace } from './widgets'

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
        budget_total_rub: 300000,
      }).replace(/\s/g, ' '), // thousands are split by a no-break space
    ).toBe('Море и пляж, горы · ноябрь, 5–7 ночей · 2 взрослых + 2 ребёнка (3 и 7 лет) · бюджет до 300 000 ₽ на всех')
    expect(describeAnswers({ budget_level: 0 })).toBe('бюджет не важен')
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
