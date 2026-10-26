import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HotelEvidence } from '@/types/api'
import { WishChips, WishProof } from './WishProof'

const evidence = (over: Partial<HotelEvidence>): HotelEvidence => ({
  wish: 'с видом на море',
  verdict: 'yes',
  quote: 'Номера с видом на море',
  note: null,
  source: 'сайт отеля',
  source_url: 'https://hotel.example',
  ...over,
})

describe('WishProof', () => {
  it('should say «нет» with the words and the source when a source says no', () => {
    render(<WishProof evidence={[evidence({ wish: 'с балконом', verdict: 'no', quote: 'Балконов в номерах нет', note: null })]} />)

    const proof = screen.getByRole('list', { name: 'Ваши пожелания' })
    expect(within(proof).getByText('нет')).toBeInTheDocument()
    expect(within(proof).queryByText('не нашёл подтверждения')).not.toBeInTheDocument()
    expect(within(proof).getByText('«Балконов в номерах нет»')).toBeInTheDocument()
    expect(within(proof).getByRole('link', { name: 'сайт отеля' })).toBeInTheDocument()
  })

  it('should link a source only when its address is a web page', () => {
    render(<WishProof evidence={[evidence({ source_url: 'javascript:alert(1)' })]} />)

    const proof = screen.getByRole('list', { name: 'Ваши пожелания' })
    expect(within(proof).queryByRole('link')).not.toBeInTheDocument()
    expect(within(proof).getByText('сайт отеля')).toBeInTheDocument()
  })

  it('should show two answers for the same wish and an empty wish without breaking', () => {
    render(<WishProof evidence={[evidence({}), evidence({ source: 'OpenStreetMap', source_url: null }), evidence({ wish: '' })]} />)

    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })
})

describe('WishChips', () => {
  it('should not count a no as confirmed and name it apart from the unchecked ones', () => {
    render(
      <WishChips
        evidence={[
          evidence({}),
          evidence({ wish: 'с балконом', verdict: 'no', quote: 'Балконов нет' }),
          evidence({ wish: 'с ванной', verdict: 'unknown', quote: null, source: null, source_url: null }),
        ]}
      />,
    )

    expect(within(screen.getByRole('list', { name: 'Подтверждено' })).getAllByRole('listitem')).toHaveLength(1)
    expect(screen.getByText('Нет: с балконом')).toBeInTheDocument()
    expect(screen.getByText('Не подтверждено: с ванной')).toBeInTheDocument()
  })
})
