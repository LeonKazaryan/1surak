import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Logo, Wordmark } from './Logo'

describe('Logo', () => {
  it('should link home and still read as one word', () => {
    render(
      <MemoryRouter>
        <Logo />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '1surak' })).toHaveAttribute('href', '/')
  })

  it('should set the wordmark in the brand font with the 1 highlighted', () => {
    const { container } = render(<Wordmark />)

    expect(container.firstChild).toHaveClass('font-brand')
    expect(screen.getByText('1')).toHaveClass('text-highlight')
  })
})
