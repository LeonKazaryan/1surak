import { cn } from '@/components/ui/utils'
import type { FlightTicket } from '@/types/api'

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
