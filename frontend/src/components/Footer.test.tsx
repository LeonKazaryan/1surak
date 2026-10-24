import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Footer } from './Footer'

describe('Footer', () => {
  it('should sit on the page background without its own band', () => {
    render(<Footer />)

    const footer = screen.getByRole('contentinfo')
    expect(footer).toHaveTextContent('1surak · команда beshparmak')
    expect(footer).not.toHaveClass('bg-white')
    expect(footer).not.toHaveClass('border-t')
  })
})
