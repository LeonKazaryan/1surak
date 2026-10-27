import { render, screen, within } from '@testing-library/react'
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
    expect(sources).toHaveTextContent('Wikivoyage')
    expect(sources).not.toHaveTextContent('https://')
    expect(screen.getByRole('link', { name: /Wikivoyage/ })).toHaveAttribute('title', expect.stringContaining('2024-05-10'))
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

  it('should turn sources written into the sentence into short badges', () => {
    const text =
      'Считаю 14 ночей из Алматы. Черногория без визы только до 1 ноября. Источники: Aviasales.kz, проверено ' +
      '26.10.2026, https://www.aviasales.kz/demalys/article/kz-bezviz; evisa.kz, проверено 26.10.2026, ' +
      'https://evisa.kz/news/puteshestvuyte-bez-ogranicheniy-29-stran-bez-viz-dlya-kazahstancev'
    render(<MessageContent text={text} />)

    expect(screen.getByText(/Черногория без визы только до 1 ноября\.$/)).toBeInTheDocument()
    const sources = screen.getByRole('list', { name: 'Источники' })
    expect(within(sources).getAllByRole('link').map((a) => a.textContent?.slice(1))).toEqual(['Aviasales.kz', 'evisa.kz'])
    expect(screen.getByRole('link', { name: /Aviasales\.kz/ })).toHaveAttribute(
      'href',
      'https://www.aviasales.kz/demalys/article/kz-bezviz',
    )
    expect(document.body).not.toHaveTextContent('https://')
  })

  it('should leave the word in an ordinary sentence alone', () => {
    render(<MessageContent text="Источники: местные жители советуют рынок." />)

    expect(screen.queryByRole('list', { name: 'Источники' })).toBeNull()
  })

  it('should show a bare address in the text as the site name', () => {
    render(<MessageContent text="Правила на https://evisa.kz/news/rules, проверьте перед поездкой." />)

    expect(screen.getByRole('link', { name: 'evisa.kz' })).toHaveAttribute('href', 'https://evisa.kz/news/rules')
    expect(screen.getByText(/проверьте перед поездкой/)).toBeInTheDocument()
  })

  it('should keep a price on one line', () => {
    const { container } = render(<MessageContent text="Билет от 72 504 ₸ и 12 775 ₽" />)

    // the prices are chips now: the paragraph as a whole still reads with no-break spaces inside them
    expect(container.querySelector('p')?.textContent).toBe('Билет от 72\u00a0504\u00a0₸ и 12\u00a0775\u00a0₽')
  })

  it('should not render raw HTML from the model', () => {
    const { container } = render(<MessageContent text={'<img src=x onerror="alert(1)">'} />)

    expect(container.querySelector('img')).toBeNull()
  })
})

describe('MessageContent highlights', () => {
  it('should mark the prices and turn the places of the cards into chips', () => {
    render(
      <MessageContent
        text={'В Анталье тепло, билет от 12 775 ₽, а в Сочи прохладнее. $185 за визу.'}
        places={[
          { id: 'antalya', name: 'Анталья', countryCode: 'TR' },
          { id: 'sochi', name: 'Сочи', countryCode: 'RU' },
        ]}
      />,
    )

    const prices = document.querySelectorAll('.price-chip')
    expect([...prices].map((p) => p.textContent)).toEqual(['от 12 775 ₽', '$185'])
    expect(screen.getByRole('link', { name: /Сочи/ })).toHaveAttribute('data-place', 'sochi')
    expect(screen.queryByRole('link', { name: /Анталья/ })).toBeNull() // «Анталье» is another form: left as text
  })

  it('should leave the text alone without cards', () => {
    render(<MessageContent text="Просто ответ без цен" />)

    expect(document.querySelector('.place-chip, .price-chip')).toBeNull()
  })
})
