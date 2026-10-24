import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ScrollRow } from './ScrollRow'

function measure(el: HTMLElement, { scrollWidth, clientWidth, scrollLeft }: Record<string, number>) {
  Object.defineProperty(el, 'scrollWidth', { configurable: true, value: scrollWidth })
  Object.defineProperty(el, 'clientWidth', { configurable: true, value: clientWidth })
  Object.defineProperty(el, 'scrollLeft', { configurable: true, value: scrollLeft })
}

describe('ScrollRow', () => {
  it('should fade only the side that has more to scroll', () => {
    render(
      <ScrollRow label="Примеры">
        <button type="button">Тёплое море</button>
        <button type="button">Казань</button>
      </ScrollRow>,
    )
    const row = screen.getByRole('group', { name: 'Примеры' })

    measure(row, { scrollWidth: 600, clientWidth: 300, scrollLeft: 0 })
    fireEvent.scroll(row)
    expect(row).toHaveAttribute('data-fade-end')
    expect(row).not.toHaveAttribute('data-fade-start')

    measure(row, { scrollWidth: 600, clientWidth: 300, scrollLeft: 300 })
    fireEvent.scroll(row)
    expect(row).toHaveAttribute('data-fade-start')
    expect(row).not.toHaveAttribute('data-fade-end')
  })

  it('should not fade anything when everything fits', () => {
    render(
      <ScrollRow label="Примеры">
        <button type="button">Казань</button>
      </ScrollRow>,
    )
    const row = screen.getByRole('group', { name: 'Примеры' })

    measure(row, { scrollWidth: 300, clientWidth: 300, scrollLeft: 0 })
    fireEvent.scroll(row)

    expect(row).not.toHaveAttribute('data-fade-start')
    expect(row).not.toHaveAttribute('data-fade-end')
  })
})
