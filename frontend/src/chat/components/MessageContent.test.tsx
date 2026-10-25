import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MessageContent } from './MessageContent'

describe('MessageContent', () => {
  it('should render markdown lists, headings and emphasis', () => {
    render(<MessageContent text={'## Варианты\n\n- **Хургада**: *море 26 °C*\n- Дубай\n\n1. Первый\n\n`код`'} />)

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

  it('should show the sources as short links instead of raw addresses', () => {
    const text = [
      'Зимой в Казани ярмарка на Кремлёвской набережной.',
      '',
      'Источники:',
      '- Wikivoyage, 2024-05-10, https://ru.wikivoyage.org/wiki/%D0%9A%D0%B0%D0%B7%D0%B0%D0%BD%D1%8C',
      '- [Visit Kazan](https://visit-kazan.ru/winter)',
    ].join('\n')
    render(<MessageContent text={text} />)

    expect(screen.getByText(/ярмарка на Кремлёвской набережной/)).toBeInTheDocument()
    const sources = screen.getByRole('list', { name: 'Источники' })
    expect(sources).toHaveTextContent('Wikivoyage, 2024-05-10')
    expect(sources).not.toHaveTextContent('https://')
    expect(screen.getByRole('link', { name: /Visit Kazan/ })).toHaveAttribute('href', 'https://visit-kazan.ru/winter')
  })

  it('should keep a closing sentence after the sources as text', () => {
    render(<MessageContent text={'Ответ\n\nИсточники:\n- Wikivoyage, https://ru.wikivoyage.org/wiki/Казань\n\nПодобрать отели?'} />)

    expect(screen.getByRole('list', { name: 'Источники' }).children).toHaveLength(1)
    expect(screen.getByText('Подобрать отели?').tagName).toBe('P')
  })

  it('should keep the brackets that belong to an address', () => {
    render(<MessageContent text={'Ответ\n\nИсточники:\n- Википедия, https://ru.wikipedia.org/wiki/Пхукет_(остров)'} />)

    expect(screen.getByRole('link', { name: /Википедия/ })).toHaveAttribute('href', 'https://ru.wikipedia.org/wiki/Пхукет_(остров)')
  })

  it('should never link a source to anything but a web address', () => {
    render(<MessageContent text={'Ответ\n\nИсточники:\n- [Клик](javascript:alert(1))'} />)

    expect(screen.queryByRole('link', { name: /Клик/ })).toBeNull()
  })

  it('should keep a price on one line', () => {
    render(<MessageContent text="Билет от 72 504 ₸ и 12 775 ₽" />)

    expect(screen.getByText(/Билет от/).textContent).toBe('Билет от 72\u00a0504\u00a0₸ и 12\u00a0775\u00a0₽')
  })

  it('should not render raw HTML from the model', () => {
    const { container } = render(<MessageContent text={'<img src=x onerror="alert(1)">'} />)

    expect(container.querySelector('img')).toBeNull()
  })
})
