import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

class NoopObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}

globalThis.IntersectionObserver = NoopObserver as unknown as typeof IntersectionObserver
globalThis.ResizeObserver = NoopObserver as unknown as typeof ResizeObserver
document.elementsFromPoint = () => []
Element.prototype.scrollIntoView = () => {}

window.matchMedia = vi.fn().mockImplementation((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  addListener: vi.fn(),
  removeListener: vi.fn(),
  dispatchEvent: vi.fn(),
}))
