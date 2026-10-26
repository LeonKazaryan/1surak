import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { RouteCard } from '@/types/api'
import { RouteCardView } from './RouteCard'
import { RouteDetails } from './RouteDetails'
import { SMART_ROUTE } from './testRoute'

const money = (text: string) => new RegExp(text.replace(/ /g, '\\s'))

describe('RouteDetails with smarter ways', () => {
  it('should show a smart way as its parts, with the train and where to buy it', () => {
    render(<RouteDetails card={SMART_ROUTE} />)

    const way = screen.getByRole('list', { name: 'Алматы → Самарканд через Ташкент' })
    expect(within(way).getByRole('link', { name: 'Алматы → Ташкент, Uzbekistan Airways' })).toHaveAttribute(
      'href',
      expect.stringContaining('aviasales.ru/search/ALA1805TAS1'),
    )
    const train = within(way).getByRole('link', { name: 'Ташкент → Самарканд, Поезд 776Ф' })
    expect(train).toHaveAttribute('href', 'https://www.tutu.ru/poezda/rasp_d.php?nnst1=2900000&nnst2=2900700')
    expect(train).toHaveTextContent('13:56 → 16:09')
    expect(within(way).getByText('пересадка в Ташкент')).toBeInTheDocument()
    expect(screen.getAllByText(/Умный путь через Ташкент/)).toHaveLength(2)
  })

  it('should strike the direct way through and show the saving', () => {
    render(<RouteDetails card={SMART_ROUTE} />)

    expect(screen.getByText(money('−25 191 ₽'))).toBeInTheDocument()
    expect(screen.getByText(/вместо Turkish Airlines, 1 пересадка, 10,5 ч/)).toBeInTheDocument()
    expect(screen.getByText(money('37 089 ₽')).closest('del')).not.toBeNull()
  })

  it('should keep each city after the leg that reaches it and count the trains in the total', () => {
    render(<RouteDetails card={SMART_ROUTE} />)

    const steps = [...screen.getByRole('list', { name: 'Маршрут' }).children].map((li) => li.textContent)
    expect(steps).toEqual([
      expect.stringContaining('Астана → Алматы'),
      expect.stringContaining('Алматы'),
      expect.stringContaining('Алматы → Самарканд'),
      expect.stringContaining('Самарканд'),
      expect.stringContaining('Самарканд → Астана'),
    ])
    expect(screen.getByText(money('в том числе поезда и автобусы на 5 061 ₽'))).toBeInTheDocument()
    expect(screen.getByText(money('Умные пересадки сберегли 63 197 ₽'), { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Даты состыкованы: 12 мая → 18 мая → 21 мая')).toBeInTheDocument()
  })
})

describe('RouteCardView', () => {
  it('should fit a tour of six cities into one banner', () => {
    const names = ['Бангкок', 'Паттайя', 'Пхукет', 'Краби', 'Фукуок', 'Нячанг']
    const stops = names.map((name, i) => ({ ...SMART_ROUTE.stops[0], id: `s${i}`, name, nights: 2 }))
    const card: RouteCard = {
      ...SMART_ROUTE,
      stops,
      legs: [...names, null].map((to, i) => ({
        from: i ? names[i - 1] : 'Астана',
        to: to ?? 'Астана',
        mode: 'flight' as const,
        km: 900,
        hours: 2,
        from_stop: i ? i - 1 : null,
        to_stop: to ? i : null,
      })),
    }
    const props = { best: false, picked: false, dimmed: false, canPick: true, onPick: () => {}, detailsOpen: false, onDetails: () => {} }

    render(<RouteCardView card={card} {...props} />)

    expect(screen.getAllByRole('heading').map((h) => h.textContent)).toEqual(names)
    expect(screen.getByText(/6 городов · 12/)).toBeInTheDocument()
  })
})
