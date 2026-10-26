import { Fragment, useContext } from 'react'
import { motion } from 'motion/react'
import { SparklesIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { GroundRide, RouteFlight, RouteLeg } from '@/types/api'
import { CurrencyContext, formatMoney, plural } from '../widgets'
import { fareOf, KIND_TONE, legKind, rideTimes, saving, units, type LegKind } from './legFormat'
import { AirlineLogo } from './ticket'
import { hours, shortDate, stopsText } from './ticketFormat'

const PLANE = 'M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z'
const SPRING = { type: 'spring', stiffness: 230, damping: 26 } as const
const GLIDE = [0.215, 0.61, 0.355, 1] as const

export function ModeIcon({ mode, className }: { mode: LegKind; className?: string }) {
  if (mode === 'flight') {
    return (
      <svg viewBox="0 0 24 24" className={cn('rotate-90', className)} aria-hidden>
        <path fill="currentColor" d={PLANE} />
      </svg>
    )
  }
  const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' } as const
  if (mode === 'train') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
        <rect x="5" y="3" width="14" height="14" rx="4" />
        <path d="M5 10.5h14M10 6.5h4M8.5 21l1.8-4M15.5 21l-1.8-4" />
        <circle cx="8.8" cy="13.8" r="0.7" fill="currentColor" />
        <circle cx="15.2" cy="13.8" r="0.7" fill="currentColor" />
      </svg>
    )
  }
  if (mode === 'bus') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
        <rect x="4.5" y="3" width="15" height="14" rx="2.5" />
        <path d="M4.5 10h15M7.5 17v3M16.5 17v3M2.5 7v3M21.5 7v3" />
        <circle cx="8" cy="13.5" r="0.7" fill="currentColor" />
        <circle cx="16" cy="13.5" r="0.7" fill="currentColor" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden {...stroke}>
      <rect x="4" y="4" width="16" height="13" rx="3" />
      <path d="M4 11h16M8 20v-3M16 20v-3" />
      <circle cx="8" cy="14" r="0.6" fill="currentColor" />
      <circle cx="16" cy="14" r="0.6" fill="currentColor" />
    </svg>
  )
}

/** The leg's kind in a round badge; on a tinted panel it sits on a card-coloured disc, so a line behind it
 * does not show through. */
function ModeBadge({ kind, className }: { kind: LegKind; className?: string }) {
  return (
    <span className={cn('flex h-8 w-8 shrink-0 rounded-full bg-card', className)}>
      <span className={cn('flex h-full w-full items-center justify-center rounded-full', KIND_TONE[kind])}>
        <ModeIcon mode={kind} className="h-4 w-4" />
      </span>
    </span>
  )
}

function FlightLine({ ticket }: { ticket: RouteFlight }) {
  return (
    <>
      <AirlineLogo ticket={ticket} className="h-4 w-4" />
      <span className="truncate">
        {ticket.airline_name} ·{' '}
        <span className={ticket.transfers === 0 ? 'font-medium text-[#4c9a2a]' : undefined}>{stopsText(ticket)}</span>
        {ticket.hours > 0 && ` · ${hours(ticket.hours)}`}
      </span>
    </>
  )
}

function RideLine({ ride }: { ride: GroundRide }) {
  const times = rideTimes(ride)
  return (
    <span className="truncate">
      {ride.name}
      {times && <span className="tabular-nums">{` · ${times}`}</span>}
      {` · ${hours(ride.hours)}`}
    </span>
  )
}

/** What one flight or hop says under its title: the airline, the train or bus, or an estimate by distance. */
function LegLine({ leg }: { leg: RouteLeg }) {
  if (leg.ticket) return <FlightLine ticket={leg.ticket} />
  if (leg.ground) return <RideLine ride={leg.ground} />
  return (
    <span className="truncate">
      {leg.mode === 'ground' ? `по земле ~${hours(leg.hours)}, ${leg.km} км` : `~${hours(leg.hours)} лёту`}
      <span className="text-faint"> · {leg.mode === 'ground' ? 'оценка' : 'билетов пока нет'}</span>
    </span>
  )
}

/** The right column: when it leaves (or the class of seat) and the fare. */
function LegPrice({ leg, small }: { leg: RouteLeg; small?: boolean }) {
  const currency = useContext(CurrencyContext)
  const fare = fareOf(leg)
  const note = leg.ticket
    ? `${shortDate(leg.ticket.departure)}${small ? `, ${leg.ticket.departure.slice(11, 16)}` : ', от'}`
    : leg.ground
      ? (leg.ground.fare ?? (leg.ground.mode === 'bus' ? 'автобус' : 'поезд'))
      : leg.estimate_rub
        ? 'оценка'
        : null
  const shown = fare ?? leg.estimate_rub ?? null
  if (shown === null && !note) return null
  return (
    <span className="shrink-0 text-right">
      {note && <span className="block text-[11px] text-faint">{note}</span>}
      {shown !== null && (
        <span className={cn('block font-semibold text-foreground tabular-nums', small ? 'text-[13px]' : 'text-[14px]')}>
          {fare === null && '~'}
          {formatMoney(shown, currency)}
        </span>
      )}
    </span>
  )
}

function linkOf(leg: RouteLeg): string | undefined {
  return leg.ticket?.link ?? leg.ground?.link
}

function labelOf(leg: RouteLeg): string {
  const by = leg.ticket?.airline_name ?? leg.ground?.name
  return by ? `${leg.from} → ${leg.to}, ${by}` : `${leg.from} → ${leg.to}`
}

function Linked({ leg, className, children }: { leg: RouteLeg; className: string; children: React.ReactNode }) {
  const href = linkOf(leg)
  if (!href) return <div className={className}>{children}</div>
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={labelOf(leg)} className={cn(className, 'transition-colors')}>
      {children}
    </a>
  )
}

function PlainLeg({ leg, index }: { leg: RouteLeg; index: number }) {
  return (
    <motion.li
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ ...SPRING, delay: 0.35 + index * 0.07 }}
      className="list-none"
    >
      <Linked leg={leg} className={cn('flex items-center gap-3 rounded-xl px-2 py-1.5', linkOf(leg) && 'hover:bg-accent/60')}>
        <ModeBadge kind={legKind(leg)} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-semibold text-foreground">
            {leg.from} → {leg.to}
          </span>
          <span className="flex min-w-0 items-center gap-1.5 text-[12px] text-muted-foreground">
            <LegLine leg={leg} />
          </span>
        </span>
        <LegPrice leg={leg} />
      </Linked>
    </motion.li>
  )
}

/** The direct way that was replaced, its price struck through as the saving pops in. */
function Instead({ leg, delay }: { leg: RouteLeg; delay: number }) {
  const currency = useContext(CurrencyContext)
  const instead = leg.instead!
  const saved = saving(leg)
  const transfers = `${instead.transfers} ${plural(instead.transfers, ['пересадка', 'пересадки', 'пересадок'])}`
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...SPRING, delay }}
      className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl bg-card/80 px-2.5 py-1.5 text-[12px] leading-snug"
    >
      {saved && (
        <motion.span
          initial={{ scale: 0.4, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 520, damping: 17, delay: delay + 0.25 }}
          className="rounded-full bg-[#4c9a2a] px-2 py-0.5 font-semibold whitespace-nowrap text-white tabular-nums"
        >
          −{formatMoney(saved, currency)}
        </motion.span>
      )}
      <span className="min-w-0 text-muted-foreground">
        {`вместо ${instead.airline}, ${transfers}, ${hours(instead.hours)}, `}
        <del className="relative whitespace-nowrap text-faint no-underline tabular-nums">
          {formatMoney(instead.price_rub, currency)}
          <motion.span
            aria-hidden
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.35, ease: GLIDE, delay: delay + 0.45 }}
            className="absolute inset-x-0 top-1/2 h-px origin-left bg-current"
          />
        </del>
      </span>
    </motion.div>
  )
}

/** A smarter way than the flight with transfers: the parts one after another on a dashed line that draws
 * itself, then what it saves against the direct way. */
function SmartLeg({ leg, index }: { leg: RouteLeg; index: number }) {
  const currency = useContext(CurrencyContext)
  const parts = units(leg)
  const kinds = [...new Set(parts.map(legKind))]
  const delay = 0.35 + index * 0.07
  const price = leg.price_rub ?? null
  return (
    <motion.li
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...SPRING, delay }}
      className="list-none"
    >
      <div className="relative overflow-hidden rounded-2xl bg-accent p-1.5 ring-1 ring-primary/70">
        <motion.span
          aria-hidden
          initial={{ x: '-120%' }}
          animate={{ x: '320%' }}
          transition={{ duration: 1.2, ease: 'easeInOut', delay: delay + 0.5 }}
          className="pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-linear-to-r from-transparent via-white/60 to-transparent"
        />
        <div className="relative flex items-center gap-3 px-1.5 pt-1">
          <span className="flex shrink-0 -space-x-3">
            {kinds.map((kind) => (
              <ModeBadge key={kind} kind={kind} className="ring-2 ring-accent" />
            ))}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-semibold text-foreground">
              {leg.from} → {leg.to}
            </span>
            <span className="flex min-w-0 items-center gap-1 text-[12px] font-medium text-[#3f7d22]">
              <SparklesIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="truncate">
                Умный путь через {leg.via} · {hours(leg.hours)}
              </span>
            </span>
          </span>
          {price !== null && (
            <span className="shrink-0 text-right">
              <span className="block text-[11px] text-faint">вместе</span>
              <span className="block text-[14px] font-semibold text-foreground tabular-nums">{formatMoney(price, currency)}</span>
            </span>
          )}
        </div>

        <ol aria-label={`${leg.from} → ${leg.to} через ${leg.via}`} className="relative m-0 mt-1 flex list-none flex-col p-0">
          <motion.span
            aria-hidden
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.5, ease: GLIDE, delay: delay + 0.15 }}
            className="absolute top-5 bottom-5 left-[21px] origin-top border-l-2 border-dashed border-[#4c9a2a]/35"
          />
          {parts.map((part, i) => (
            <Fragment key={`${part.from}-${part.to}`}>
              {i > 0 && (
                <motion.li
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3, delay: delay + 0.2 + i * 0.12 }}
                  className="list-none py-0.5 pl-12 text-[11px] font-medium text-[#3f7d22]"
                >
                  пересадка в {part.from}
                </motion.li>
              )}
              <motion.li
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ ...SPRING, delay: delay + 0.15 + i * 0.12 }}
                className="relative list-none"
              >
                <Linked leg={part} className={cn('flex items-center gap-3 rounded-xl px-1.5 py-1', linkOf(part) && 'hover:bg-card/70')}>
                  <ModeBadge kind={legKind(part)} className="relative ring-4 ring-accent" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium text-foreground">
                      {part.from} → {part.to}
                    </span>
                    <span className="flex min-w-0 items-center gap-1.5 text-[12px] text-muted-foreground">
                      <LegLine leg={part} />
                    </span>
                  </span>
                  <LegPrice leg={part} small />
                </Linked>
              </motion.li>
            </Fragment>
          ))}
        </ol>

        {leg.instead && <Instead leg={leg} delay={delay + 0.35 + parts.length * 0.12} />}
      </div>
    </motion.li>
  )
}

export function LegRow({ leg, index }: { leg: RouteLeg; index: number }) {
  return leg.parts?.length ? <SmartLeg leg={leg} index={index} /> : <PlainLeg leg={leg} index={index} />
}
