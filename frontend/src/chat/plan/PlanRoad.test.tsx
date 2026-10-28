import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { PlanLeg } from '@/types/api'
import { SMART_ROUTE } from '../components/testRoute'
import { PlanRoad } from './PlanRoad'

const home: PlanLeg = { ...SMART_ROUTE.legs[2], departs: '2027-05-21T00:33', arrives: '2027-05-21T18:20', ground_rub: null }

describe('PlanRoad', () => {
  it('should give each part of a smart way its own place to buy, for the whole party', () => {
    render(<PlanRoad legs={[home]} checks={[]} seats={2} />)

    const [leg] = screen.getAllByRole('list').map((list) => list.parentElement!)
    expect(within(leg).getByText(/Умный путь через Ташкент/)).toBeInTheDocument()
    expect(within(leg).getByRole('link', { name: 'Поезд Самарканд → Ташкент на Туту.ру' })).toHaveTextContent(
      'Расписание и билеты на Туту.ру',
    )
    expect(within(leg).getByRole('link', { name: 'Купить билет Ташкент → Астана' })).toHaveAttribute(
      'href',
      expect.stringContaining('/search/TAS2105NQZ2'),
    )
    expect(within(leg).getByText(/8\s858\s₽/)).toBeInTheDocument()
    expect(within(leg).getByText('× 2')).toBeInTheDocument()
  })
})
