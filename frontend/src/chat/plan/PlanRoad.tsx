import { useContext } from 'react'
import { ArrowTopRightOnSquareIcon, SparklesIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { PlanCheck, PlanLeg, RouteLeg } from '@/types/api'
import { CurrencyContext, formatMoney } from '../widgets'
import { ModeIcon } from '../components/LegRow'
import { Credit } from '../components/Credit'
import { fareOf, KIND_TONE, knownFare, legKind, rideAction, rideShop, rideTimes, saving, units } from '../components/legFormat'
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

const BUY = 'mt-1.5 inline-flex h-7 items-center gap-1 rounded-full px-2.5 text-[12px] font-medium transition-colors'

/** The airline or the train, and where to buy it. */
function UnitInfo({ leg, seats }: { leg: RouteLeg; seats: number }) {
  const ticket = leg.ticket
  const ride = leg.ground
  if (ticket) {
    return (
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
            className={cn(BUY, 'bg-highlight/10 text-highlight hover:bg-highlight/20')}
          >
            Купить на Aviasales
            <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" aria-hidden />
          </a>
        )}
      </>
    )
  }
  if (ride) {
    const times = rideTimes(ride)
    return (
      <>
        <span className="mt-1 block text-[12px] leading-snug text-muted-foreground">
          {ride.name}
          {times && <span className="whitespace-nowrap tabular-nums">{` · ${times}`}</span>}
          <span className="whitespace-nowrap">{` · ${hours(ride.hours)}`}</span>
          {ride.fare && ` · ${ride.fare}`}
        </span>
        <a
          href={ride.link}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${ride.mode === 'bus' ? 'Автобус' : 'Поезд'} ${leg.from} → ${leg.to} на ${rideShop(ride)}`}
          className={cn(BUY, 'bg-primary/40 text-[#2f6418] hover:bg-primary/60')}
        >
          {rideAction(ride)}
          <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" aria-hidden />
        </a>
        {ride.credit && <Credit credit={ride.credit} className="mt-1" />}
      </>
    )
  }
  return (
    <span className="mt-1 block text-[12px] text-muted-foreground">
      {leg.mode === 'flight' ? 'билетов пока нет' : `по земле, ${leg.km} км: поезд, автобус или такси`}
    </span>
  )
}

function Price({ rub, note, estimate }: { rub: number; note: string; estimate?: boolean }) {
  const currency = useContext(CurrencyContext)
  return (
    <span className="shrink-0 text-right">
      <span className="block text-[15px] font-semibold text-foreground tabular-nums">
        {estimate && '~'}
        {formatMoney(rub, currency)}
      </span>
      <span className="block text-[11px] text-faint">{note}</span>
    </span>
  )
}

function Badge({ leg, size = 'h-9 w-9' }: { leg: RouteLeg; size?: string }) {
  const kind = legKind(leg)
  return (
    <span className={cn('mt-0.5 flex shrink-0 items-center justify-center rounded-full', size, KIND_TONE[kind])}>
      <ModeIcon mode={kind} className="h-4 w-4" />
    </span>
  )
}

/** A smarter way: the parts, each with its own ticket or train, and what it saves against the direct way. */
function SmartParts({ leg, seats }: { leg: PlanLeg; seats: number }) {
  const currency = useContext(CurrencyContext)
  const saved = saving(leg)
  return (
    <>
      <span className="mt-1 flex items-center gap-1 text-[12px] font-medium text-[#3f7d22]">
        <SparklesIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
        {`Умный путь через ${leg.via}`}
        {saved && <span className="ml-1 rounded-full bg-[#4c9a2a] px-1.5 text-[11px] text-white tabular-nums">−{formatMoney(saved, currency)}</span>}
      </span>
      <ol className="m-0 mt-2 flex list-none flex-col gap-3 border-l-2 border-dashed border-[#4c9a2a]/30 p-0 pl-3">
        {units(leg).map((part) => (
          <li key={`${part.from}-${part.to}`} className="flex items-start gap-2.5">
            <Badge leg={part} size="h-7 w-7" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-foreground">{`${part.from} → ${part.to}`}</span>
              <UnitInfo leg={part} seats={seats} />
            </span>
          </li>
        ))}
      </ol>
    </>
  )
}

function LegRow({ leg, seats }: { leg: PlanLeg; seats: number }) {
  const smart = Boolean(leg.parts?.length)
  const fare = smart ? (leg.price_rub ?? knownFare(leg)) : fareOf(leg)
  const each = seats > 1 ? `× ${seats}` : smart ? 'вместе' : 'за билет'
  return (
    <li className="flex items-start gap-3">
      <Badge leg={smart ? units(leg)[0] : leg} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] leading-snug font-semibold text-foreground">{`${leg.from} → ${leg.to}`}</span>
        <span className="block text-[13px] leading-snug text-muted-foreground">{when(leg)}</span>
        {smart ? <SmartParts leg={leg} seats={seats} /> : <UnitInfo leg={leg} seats={seats} />}
      </span>
      {fare ? <Price rub={fare} note={each} /> : leg.ground_rub ? <Price rub={leg.ground_rub} note="на человека" estimate /> : null}
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
