import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MessageContent } from './MessageContent'

describe('MessageContent', () => {
  it('should render markdown lists, headings and emphasis', () => {
    render(<MessageContent text={'## Варианты\n\n- **Хургада** — *море 26 °C*\n- Дубай\n\n1. Первый\n\n`код`'} />)

    expect(screen.getByRole('heading', { name: 'Варианты' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    expect(screen.getByText('Хургада').tagName).toBe('STRONG')
    expect(screen.getByText('море 26 °C').tagName).toBe('EM')
    expect(screen.getByText('код').tagName).toBe('CODE')
  })

  it('should open links in a new tab without leaking the opener', () => {
    render(<MessageContent text="[Погода](https://open-meteo.com)" />)

    const link = screen.getByRole('link', { name: 'Погода' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('should not render raw HTML from the model', () => {
    const { container } = render(<MessageContent text={'<img src=x onerror="alert(1)">'} />)

    expect(container.querySelector('img')).toBeNull()
  })
})
