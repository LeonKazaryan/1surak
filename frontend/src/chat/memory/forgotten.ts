/** localStorage list of the memory facts the traveller hid: sent with every request, so nothing hidden is used. */

const KEY = '1surak.forgotten'
const MAX_KEYS = 60

export function getForgotten(): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter((key): key is string => typeof key === 'string') : []
  } catch {
    return []
  }
}

export function forgetFact(key: string): void {
  try {
    localStorage.setItem(KEY, JSON.stringify([key, ...getForgotten().filter((k) => k !== key)].slice(0, MAX_KEYS)))
  } catch {
    // Storage blocked (private mode): the fact is hidden until the page reloads.
  }
}
