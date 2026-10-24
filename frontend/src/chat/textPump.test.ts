import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createTextPump } from './textPump'

let frames: FrameRequestCallback[] = []

function flushFrames() {
  while (frames.length) {
    const pending = frames
    frames = []
    pending.forEach((cb) => cb(0))
  }
}

beforeEach(() => {
  frames = []
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
  vi.stubGlobal('cancelAnimationFrame', () => {
    frames = []
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createTextPump', () => {
  it('should reveal pushed text gradually until all of it is shown', () => {
    const shown: string[] = []
    const pump = createTextPump((text) => shown.push(text))

    pump.push('Привет, ')
    pump.push('как дела?')
    flushFrames()

    expect(shown.at(-1)).toBe('Привет, как дела?')
    expect(shown.length).toBeGreaterThan(1)
    expect(pump.text()).toBe('Привет, как дела?')
  })

  it('should catch up faster when far behind', () => {
    const shown: string[] = []
    const pump = createTextPump((text) => shown.push(text))

    pump.push('x'.repeat(1000))
    flushFrames()

    expect(shown.at(-1)).toHaveLength(1000)
    expect(shown.length).toBeLessThan(60)
  })

  it('should stop revealing after stop is called', () => {
    const shown: string[] = []
    const pump = createTextPump((text) => shown.push(text))

    pump.push('x'.repeat(100))
    pump.stop()
    flushFrames()

    expect(shown).toEqual([])
    expect(pump.text()).toHaveLength(100)
  })
})
