import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TripPrompt } from './TripPrompt'

describe('TripPrompt', () => {
  it('should show a search icon in front of the input', () => {
    render(<TripPrompt value="" onChange={vi.fn()} onSubmit={vi.fn()} />)

    const input = screen.getByRole('textbox', { name: 'Опишите поездку' })
    const icon = input.previousElementSibling

    expect(icon?.tagName).toBe('svg')
    expect(icon).toHaveAttribute('aria-hidden', 'true')
  })
})
