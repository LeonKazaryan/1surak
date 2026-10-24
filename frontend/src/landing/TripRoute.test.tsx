import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TripRoute } from './TripRoute'

const MOTION_OK = '(prefers-reduced-motion: no-preference)'

const defaultMatchMedia = window.matchMedia

function allowMotion() {
  window.matchMedia = vi.fn((query: string) => ({
    matches: query === MOTION_OK,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

afterEach(() => {
  window.matchMedia = defaultMatchMedia
})

function renderRoute() {
  return render(
    <MemoryRouter>
      <TripRoute />
    </MemoryRouter>,
  )
}

describe('TripRoute', () => {
  it('should fly the route on any screen size when motion is allowed', () => {
    allowMotion()

    renderRoute()

    expect(screen.getByTestId('trip-flight')).toBeInTheDocument()
  })

  it('should show a plain route when the user prefers less motion', () => {
    renderRoute()

    expect(screen.queryByTestId('trip-flight')).not.toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Шаги поездки' })).toBeInTheDocument()
  })

  it('should walk through the steps and end with a way to start planning', () => {
    render(
      <MemoryRouter>
        <TripRoute />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 2, name: 'Как это работает' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'Пишете как есть',
      'Агент собирает поездку',
      'Объясняет выбор',
      'Поездка готова',
    ])
    expect(screen.getByRole('link', { name: 'Спланировать поездку' })).toHaveAttribute('href', '/chat')
  })
})
