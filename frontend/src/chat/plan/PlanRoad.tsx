import { useContext } from 'react'
import { ArrowTopRightOnSquareIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { PlanCheck, PlanLeg } from '@/types/api'
import { CurrencyContext, formatMoney } from '../widgets'
import { ModeIcon } from '../components/RouteCard'
import { AirlineLogo } from '../components/ticket'
import { forPassengers, hours, stopsText } from '../components/ticketFormat'
import { CheckRow, PlanSection } from './planParts'
import { clock, dayChip, dayText } from './planFormat'

function when(leg: PlanLeg): string {
  if (!leg.departs) return 'дату и время уточню, когда появятся билеты на эти даты'
  const day = dayChip(leg.departs)
  const times = [clock(leg.departs), clock(leg.arrives)].filter(Boolean).join(' → ')
  return `${day.weekday}, ${dayText(leg.departs)} · ${times}`
}

function LegRow({ leg, seats }: { leg: PlanLeg; seats: number }) {
  const currency = useContext(CurrencyContext)
  const ticket = leg.ticket
  const flight = leg.mode === 'flight'
  return (
    <li className="flex items-start gap-3">
      <span
        className={cn(
          'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
          flight ? 'bg-highlight/10 text-highlight' : 'bg-primary/40 text-[#3f7d22]',
        )}
      >
        <ModeIcon mode={leg.mode} className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] leading-snug font-semibold text-foreground">{`${leg.from} → ${leg.to}`}</span>
        <span className="block text-[13px] leading-snug text-muted-foreground">{when(leg)}</span>
        {ticket ? (
          <>
            <span className="mt-1 flex min-w-0 items-start gap-1.5 text-[12px] leading-snug text-muted-foreground">
              <AirlineLogo ticket={ticket} className="h-4 w-4" />
              <span className="min-w-0">
                {`${ticket.airline_name} ${ticket.flight_number} · `}
                <span className={ticket.transfers === 0 ? 'font-medium text-[#4c9a2a]' : undefined}>{stopsText(ticket)}</span>
                {ticket.hours > 0 && <span className="whitespace-nowrap">{` · ${hours(ticket.hours)}`}</span>}
              </span>
            </span>
            {ticket.link && (
              <a
                href={forPassengers(ticket.link, seats)}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Купить билет ${leg.from} → ${leg.to} на Aviasales`}
                className="mt-1.5 inline-flex h-7 items-center gap-1 rounded-full bg-highlight/10 px-2.5 text-[12px] font-medium text-highlight transition-colors hover:bg-highlight/20"
              >
                Купить на Aviasales
                <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" aria-hidden />
              </a>
            )}
          </>
        ) : (
          <span className="mt-1 block text-[12px] text-muted-foreground">
            {flight ? 'билетов пока нет' : `по земле, ${leg.km} км: поезд, автобус или такси`}
          </span>
        )}
      </span>
      <span className="shrink-0 text-right">
        {ticket ? (
          <>
            <span className="block text-[15px] font-semibold text-foreground tabular-nums">{formatMoney(ticket.price_rub, currency)}</span>
            <span className="block text-[11px] text-faint">{seats > 1 ? `× ${seats}` : 'за билет'}</span>
          </>
        ) : leg.ground_rub ? (
          <>
            <span className="block text-[15px] font-semibold text-foreground tabular-nums">~{formatMoney(leg.ground_rub, currency)}</span>
            <span className="block text-[11px] text-faint">на человека</span>
          </>
        ) : null}
      </span>
    </li>
  )
}

interface PlanRoadProps {
  legs: PlanLeg[]
  checks: PlanCheck[]
  seats: number
}

/** The legs with their local times, then what was checked where they meet: landing, check-in, check-out. */
export function PlanRoad({ legs, checks, seats }: PlanRoadProps) {
  return (
    <PlanSection title="Дорога">
      <ol className="m-0 flex list-none flex-col gap-4 p-0">
        {legs.map((leg) => (
          <LegRow key={`${leg.from}-${leg.to}-${leg.departs}`} leg={leg} seats={seats} />
        ))}
      </ol>
      {checks.length > 0 && (
        <ul aria-label="Проверил стыковки" className="m-0 mt-1 flex list-none flex-col gap-3 rounded-2xl bg-inset p-4">
          {checks.map((check, i) => (
            <CheckRow key={`${i}-${check.title}`} check={check} />
          ))}
        </ul>
      )}
    </PlanSection>
  )
}
