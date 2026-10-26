/** The currency prices are shown in: picked by the user, or null to follow the departure city's country. */
export type CurrencyCode = 'RUB' | 'KZT' | 'BYN' | 'UZS' | 'KGS' | 'USD' | 'EUR'

export const CURRENCY_OPTIONS: { code: CurrencyCode; sign: string; name: string }[] = [
  { code: 'RUB', sign: '₽', name: 'Рубли' },
  { code: 'KZT', sign: '₸', name: 'Тенге' },
  { code: 'USD', sign: '$', name: 'Доллары' },
  { code: 'EUR', sign: '€', name: 'Евро' },
  { code: 'BYN', sign: 'Br', name: 'Белорусские рубли' },
  { code: 'UZS', sign: 'сум', name: 'Сумы' },
  { code: 'KGS', sign: 'сом', name: 'Сомы' },
]

const KEY = '1surak.currency'
const CHANGED = '1surak:currency'
let unsaved: CurrencyCode | null = null // when storage is blocked, the choice lasts until a reload

export function getCurrencyChoice(): CurrencyCode | null {
  try {
    const raw = localStorage.getItem(KEY)
    return CURRENCY_OPTIONS.some((o) => o.code === raw) ? (raw as CurrencyCode) : unsaved
  } catch {
    return unsaved
  }
}

export function saveCurrencyChoice(code: CurrencyCode | null): void {
  unsaved = code
  try {
    if (code) localStorage.setItem(KEY, code)
    else localStorage.removeItem(KEY)
  } catch {
    // storage blocked: `unsaved` keeps it for this page
  }
  window.dispatchEvent(new CustomEvent(CHANGED))
}

export function onCurrencyChange(listener: () => void): () => void {
  window.addEventListener(CHANGED, listener)
  return () => window.removeEventListener(CHANGED, listener)
}
