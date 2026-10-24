import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { DepartureCityPicker } from './DepartureCityPicker'

beforeEach(() => localStorage.clear())

describe('DepartureCityPicker', () => {
  it('should show the saved departure city', () => {
    localStorage.setItem('1surak.departureCity', 'LED')

    render(<DepartureCityPicker />)

    expect(screen.getByRole('combobox', { name: 'Город вылета: Санкт-Петербург' })).toHaveTextContent(/^Петербург$/)
  })

  it('should switch and remember the city picked from the list', async () => {
    const user = userEvent.setup()
    render(<DepartureCityPicker />)

    await user.click(screen.getByRole('combobox', { name: 'Город вылета: Москва' }))
    await user.click(await screen.findByRole('option', { name: 'Казань' }))

    expect(screen.getByRole('combobox', { name: 'Город вылета: Казань' })).toHaveTextContent('Казань')
    expect(localStorage.getItem('1surak.departureCity')).toBe('KZN')
  })
})
