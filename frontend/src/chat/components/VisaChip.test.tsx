import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '@/api/client'
import type { VisaFee, VisaInfo } from '@/types/api'
import { CurrencyContext } from '../widgets'
import { VisaChip } from './VisaChip'

vi.mock('@/api/client', () => ({ fetchVisa: vi.fn() }))

const KZT = { code: 'KZT', sign: '₸', glyph: '₸', per_rub: 5.561828 }
const FEE: VisaFee = {
  amount: 185,
  currency: 'USD',
  covers: 'консульский сбор за туристическую визу B1/B2',
  rub: 14_900,
  source: 'travel.state.gov',
  url: 'https://travel.state.gov/fees',
  checked: '2026-10-26',
}

function usa(pair: string, fee?: VisaFee | null): VisaInfo {
  return {
    rule: 'visa_required',
    label: 'нужна виза',
    text: 'Для граждан Казахстана нужна виза в США, её оформляют заранее в консульстве или визовом центре.',
    days: null,
    pair,
    fee,
  }
}

function renderChips(...infos: VisaInfo[]) {
  return render(
    <CurrencyContext value={KZT}>
      <ul>
        {infos.map((info, i) => (
          <VisaChip key={i} info={info} />
        ))}
      </ul>
    </CurrencyContext>,
  )
}

describe('VisaChip', () => {
  beforeEach(() => vi.mocked(client.fetchVisa).mockReset())

  it('should tell what the passport needs and fetch the fee once for every card of the country', async () => {
    let answer!: (info: VisaInfo) => void
    vi.mocked(client.fetchVisa).mockReturnValue(new Promise((resolve) => (answer = resolve)))
    renderChips(usa('KZ-US'), usa('KZ-US'))

    const [first, second] = screen.getAllByRole('button', { name: 'нужна виза' })
    await userEvent.hover(first)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Для граждан Казахстана нужна виза в США')
    expect(screen.getByText('Ищу стоимость в открытых источниках…')).toBeInTheDocument()

    answer({ ...usa('KZ-US'), fee: FEE })
    expect(await screen.findByText('185 $', { exact: false })).toBeInTheDocument()
    expect(screen.getByText(/≈ 82\s871\s₸/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /travel\.state\.gov/ })).toHaveAttribute('href', 'https://travel.state.gov/fees')

    await userEvent.unhover(first)
    await userEvent.hover(second)
    expect(client.fetchVisa).toHaveBeenCalledTimes(1)
  })

  it('should list the countries one Schengen visa opens and those that let it in', async () => {
    const schengen: VisaInfo = {
      ...usa('KZ-GR', FEE),
      label: 'нужна многократная виза',
      name: 'Шенген',
      countries: ['Греция', 'Италия'],
      also: [{ name: 'Черногория', days: 30, source: 'gov.me', url: 'https://www.gov.me/visa' }],
    }
    render(
      <CurrencyContext value={KZT}>
        <ul>
          <VisaChip info={schengen} prefix="Шенген: " />
        </ul>
      </CurrencyContext>,
    )

    await userEvent.hover(screen.getByRole('button', { name: 'Шенген: нужна многократная виза' }))

    const tooltip = screen.getByRole('tooltip')
    expect(tooltip).toHaveTextContent('Шенген: нужна многократная виза')
    expect(screen.getByRole('list', { name: 'Одна виза на страны' })).toHaveTextContent('ГрецияИталия')
    const takes = screen.getByRole('list', { name: 'По этой визе пускают' })
    expect(takes).toHaveTextContent('Черногория')
    expect(takes).toHaveTextContent('до 30 дн.')
    expect(screen.getByRole('link', { name: /gov\.me/ })).toHaveAttribute('href', 'https://www.gov.me/visa')
  })

  it('should show a fee the card already has without asking', async () => {
    renderChips(usa('KZ-CA', FEE))

    await userEvent.hover(screen.getByRole('button', { name: 'нужна виза' }))

    expect(screen.getByText('185 $', { exact: false })).toBeInTheDocument()
    expect(client.fetchVisa).not.toHaveBeenCalled()
  })

  it('should say a free visa is free and ask nothing where no visa is needed', async () => {
    renderChips(usa('KZ-JP', { ...FEE, amount: 0, currency: 'JPY', rub: 0 }), {
      ...usa('KZ-GE'),
      rule: 'visa_free',
      label: 'без визы до 360 дней',
      text: 'Для граждан Казахстана виза в Грузию не нужна, можно остаться до 360 дней.',
    })

    await userEvent.hover(screen.getByRole('button', { name: 'нужна виза' }))
    expect(screen.getByRole('tooltip')).toHaveTextContent('бесплатно')

    await userEvent.hover(screen.getByRole('button', { name: 'без визы до 360 дней' }))
    expect(await screen.findByText(/можно остаться до 360 дней/)).toBeInTheDocument()
    expect(client.fetchVisa).not.toHaveBeenCalled()
  })

  it('should say so when no open source names the fee', async () => {
    vi.mocked(client.fetchVisa).mockResolvedValue({ ...usa('KZ-MM'), fee: null })
    renderChips(usa('KZ-MM'))

    await userEvent.click(screen.getByRole('button', { name: 'нужна виза' }))

    expect(await screen.findByText(/Стоимость не нашлась в открытых источниках/)).toBeInTheDocument()
  })
})
