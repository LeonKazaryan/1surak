import { useContext } from 'react'
import { cn } from '@/components/ui/utils'
import type { FlightTicket, PriceChange } from '@/types/api'
import { CurrencyContext, formatMoney } from '../widgets'
import { shortDate } from './ticketFormat'

export function AirlineLogo({ ticket, className }: { ticket: FlightTicket; className?: string }) {
  return (
    <img
      src={ticket.logo}
      srcSet={`${ticket.logo.replace('/64/64/', '/128/128/')} 2x`}
      alt=""
      loading="lazy"
      className={cn('shrink-0 rounded-md bg-white object-contain ring-1 ring-border', className)}
      onError={(e) => (e.currentTarget.style.visibility = 'hidden')}
    />
  )
}

/** How the price moved since the trip was last priced: dearer in red, cheaper in green. */
export function PriceChangeNote({ change, className }: { change: PriceChange; className?: string }) {
  const currency = useContext(CurrencyContext)
  const since = `с ${shortDate(change.since)}`
  const moved = Math.round(change.rub * currency.per_rub)
  const text =
    moved > 0
      ? `дороже на ${formatMoney(change.rub, currency)} ${since}`
      : moved < 0
        ? `дешевле на ${formatMoney(-change.rub, currency)} ${since}`
        : `цена та же ${since}`
  const tone = moved > 0 ? 'text-danger' : moved < 0 ? 'text-[#4c9a2a]' : 'text-faint'
  return <span className={cn('text-[11px] font-medium', tone, className)}>{text}</span>
}
