import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { BudgetStep, MonthStep, OriginStep } from './questions'

const KZT = { code: 'KZT', sign: '₸', glyph: '₸', per_rub: 5.561828 }

describe('BudgetStep', () => {
  it('should show the budget levels in the user currency', () => {
    render(<BudgetStep level={null} onLevel={() => {}} onTotal={() => {}} currency={KZT} />)

    expect(screen.getByRole('button', { name: /Экономно/ })).toHaveTextContent(/до 390\s000 ₸ на человека/)
  })

  it('should draw the any-budget option with grey signs, not a sparkle', () => {
    render(<BudgetStep level={null} onLevel={() => {}} onTotal={() => {}} currency={KZT} />)

    const any = screen.getByRole('button', { name: /Не важно/ })
    expect(any).not.toHaveTextContent('✦')
    const signs = within(any).getAllByText('₸')
    expect(signs).toHaveLength(3)
    signs.forEach((sign) => expect(sign).toHaveClass('text-faintest'))
  })

  it('should open on the sum the user already named, ready to confirm', async () => {
    const onTotal = vi.fn()
    render(<BudgetStep level={null} total={500000} onLevel={() => {}} onTotal={onTotal} currency={KZT} />)

    expect(screen.getByRole('textbox', { name: 'Бюджет на всех, ₸' })).toHaveValue('500\u00a0000')
    await userEvent.click(screen.getByRole('button', { name: 'Готово' }))

    expect(onTotal).toHaveBeenCalledWith(500000)
  })

  it('should take a custom total in the user currency', async () => {
    const onTotal = vi.fn()
    render(<BudgetStep level={null} onLevel={() => {}} onTotal={onTotal} currency={KZT} />)

    await userEvent.click(screen.getByRole('button', { name: 'Указать свою сумму' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Бюджет на всех, ₸' }), '500000{Enter}')

    expect(onTotal).toHaveBeenCalledWith(500000)
  })
})

describe('MonthStep', () => {
  it('should show the year under every month, this year too', () => {
    render(<MonthStep selected={null} onPick={() => {}} />)

    const months = screen.getAllByRole('button')
    expect(months).toHaveLength(12)
    months.forEach((month) => expect(month).toHaveTextContent(/\d{4}$/))
  })
})

describe('OriginStep', () => {
  it('should keep the guessed city with one tap', async () => {
    const onPick = vi.fn()
    render(<OriginStep selected={null} guess={{ code: 'MOW', name: 'Москва' }} onPick={onPick} />)

    await userEvent.click(screen.getByRole('button', { name: /Москва/ }))

    expect(onPick).toHaveBeenCalledWith({ code: 'MOW', name: 'Москва' })
  })
})
