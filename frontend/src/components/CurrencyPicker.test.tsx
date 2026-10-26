import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { saveDepartureCity } from '@/lib/departureCity'
import { CurrencyPicker } from './CurrencyPicker'

beforeEach(() => localStorage.clear())

describe('CurrencyPicker', () => {
  it('should show the departure city currency sign while it follows the city', () => {
    localStorage.setItem('1surak.departureCity', JSON.stringify({ code: 'NQZ', name: 'Астана', country: 'Казахстан' }))
    render(<CurrencyPicker />)

    const button = screen.getByRole('button', { name: 'Валюта: Тенге, по городу вылета' })
    expect(button).toHaveTextContent('₸')
    expect(button).not.toHaveTextContent('Валюта')
  })

  it('should follow a new departure city', () => {
    localStorage.setItem('1surak.departureCity', JSON.stringify({ code: 'NQZ', name: 'Астана', country: 'Казахстан' }))
    render(<CurrencyPicker />)

    act(() => saveDepartureCity({ code: 'IST', name: 'Стамбул', country: 'Турция' }))

    expect(screen.getByRole('button', { name: 'Валюта: Доллары, по городу вылета' })).toHaveTextContent('$')
  })

  it('should show the picked currency over the city one', async () => {
    localStorage.setItem('1surak.departureCity', JSON.stringify({ code: 'NQZ', name: 'Астана', country: 'Казахстан' }))
    render(<CurrencyPicker />)

    await userEvent.click(screen.getByRole('button', { name: /Валюта/ }))
    await userEvent.click(screen.getByRole('option', { name: /Евро/ }))

    expect(screen.getByRole('button', { name: 'Валюта: Евро' })).toHaveTextContent('€')
  })
})
