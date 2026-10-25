import { useState } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import { CheckBadgeIcon, CheckIcon, ChevronDownIcon, IdentificationIcon, MinusIcon, SparklesIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { RouteCard as Route, RouteLeg, RouteStop, TripKind } from '@/types/api'
import { flagEmoji, formatRub, plural } from '../widgets'
import { AirlineLogo } from './ticket'
import { hours, shortDate, stopsText, temp } from './ticketFormat'
import { TripArt } from './TripArt'

const PLANE = 'M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z'
const SPRING = { type: 'spring', stiffness: 230, damping: 26 } as const
const MERGE_AFTER_MS = 140 // the stop cards land first, then close up into one route

/** The route rises like any card, but as separate city cards: they merge once it has landed. */
const routeRise: Variants = {
  hidden: { opacity: 0, y: 32 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 220, damping: 24 } },
}

/** A different scene for neighbouring cities, so two city stops do not look like one long skyline.
 *  Stops with the fewest kinds choose first: Samarkand is only a city, so Almaty shows its mountains. */
function sceneKinds(stops: RouteStop[]): TripKind[] {
  const kinds: (TripKind | undefined)[] = stops.map(() => undefined)
  const order = stops.map((_, i) => i).sort((a, b) => stops[a].kinds.length - stops[b].kinds.length)
  for (const i of order) {
    const taken = [kinds[i - 1], kinds[i + 1]]
    kinds[i] = stops[i].kinds.find((k) => !taken.includes(k)) ?? stops[i].kinds[0] ?? 'city'
  }
  return kinds as TripKind[]
}

function ModeIcon({ mode, className }: { mode: RouteLeg['mode']; className?: string }) {
  if (mode === 'flight') {
    return (
      <svg viewBox="0 0 24 24" className={cn('rotate-90', className)} aria-hidden>
        <path fill="currentColor" d={PLANE} />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <rect x="4" y="4" width="16" height="13" rx="3" />
      <path d="M4 11h16M8 20v-3M16 20v-3" />
      <circle cx="8" cy="14" r="0.6" fill="currentColor" />
      <circle cx="16" cy="14" r="0.6" fill="currentColor" />
    </svg>
  )
}

/** How well the route covers what the user wants, as a ring that fills in once the card is whole. */
function MatchRing({ value, on }: { value: number; on: boolean }) {
  return (
    <span className="flex items-center gap-2 rounded-full bg-white/90 py-1 pr-3 pl-1 shadow-sm backdrop-blur" title="Совпадение с интересами">
      <span className="relative h-8 w-8">
        <svg viewBox="0 0 36 36" className="h-8 w-8 -rotate-90" aria-hidden>
          <circle cx="18" cy="18" r="14" fill="none" stroke="var(--secondary)" strokeWidth="4" />
          <motion.circle
            cx="18" cy="18" r="14" fill="none" stroke="var(--primary)" strokeWidth="4" strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: on ? value / 100 : 0 }}
            transition={{ duration: 0.9, ease: 'easeOut', delay: 0.25 }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-foreground tabular-nums">
          {value}
        </span>
      </span>
      <span className="text-[12px] leading-tight font-medium text-foreground">
        совпадение
        <br />
        <span className="text-muted-foreground">с интересами</span>
      </span>
    </span>
  )
}

function LegRow({ leg, index }: { leg: RouteLeg; index: number }) {
  const ticket = leg.ticket
  const body = (
    <>
      <span
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          leg.mode === 'flight' ? 'bg-highlight/10 text-highlight' : 'bg-primary/40 text-[#3f7d22]',
        )}
      >
        <ModeIcon mode={leg.mode} className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold text-foreground">
          {leg.from} → {leg.to}
        </span>
        <span className="flex min-w-0 items-center gap-1.5 text-[12px] text-muted-foreground">
          {ticket ? (
            <>
              <AirlineLogo ticket={ticket} className="h-4 w-4" />
              <span className="truncate">
                {ticket.airline_name} ·{' '}
                <span className={ticket.transfers === 0 ? 'font-medium text-[#4c9a2a]' : undefined}>{stopsText(ticket)}</span>
                {ticket.hours > 0 && ` · ${hours(ticket.hours)}`}
              </span>
            </>
          ) : (
            <span className="truncate">
              {leg.mode === 'ground' ? `по земле ~${hours(leg.hours)}, ${leg.km} км` : `~${hours(leg.hours)} лёту`}
              <span className="text-faint"> · {leg.mode === 'ground' ? 'оценка' : 'билетов пока нет'}</span>
            </span>
          )}
        </span>
      </span>
      {ticket && (
        <span className="shrink-0 text-right">
          <span className="block text-[11px] text-faint">{shortDate(ticket.departure)}, от</span>
          <span className="block text-[14px] font-semibold text-foreground tabular-nums">{formatRub(ticket.price_rub)}</span>
        </span>
      )}
    </>
  )
  return (
    <motion.li
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ ...SPRING, delay: 0.35 + index * 0.07 }}
      className="list-none"
    >
      {ticket ? (
        <a
          href={ticket.link}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${leg.from} → ${leg.to}, ${ticket.airline_name}`}
          className="flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-accent/60"
        >
          {body}
        </a>
      ) : (
        <div className="flex items-center gap-3 px-2 py-1.5">{body}</div>
      )}
    </motion.li>
  )
}

interface RouteCardProps {
  card: Route
  best: boolean
  picked: boolean
  dimmed: boolean
  canPick: boolean
  onPick: () => void
}

/** A multi-city route across two cells of the grid: its cities arrive as separate cards and merge into one. */
export function RouteCardView({ card, best, picked, dimmed, canPick, onPick }: RouteCardProps) {
  const [merged, setMerged] = useState(false)
  const [open, setOpen] = useState(false)
  const between = card.legs.slice(1, -1) // home → first and last → home are not seams of the banner
  const nights = card.stops.reduce((sum, s) => sum + s.nights, 0)
  const countries = [...new Map(card.stops.map((s) => [s.country, s])).values()]
  const scenes = sceneKinds(card.stops)
  const flightDays = card.legs.flatMap((leg) => (leg.ticket ? [shortDate(leg.ticket.departure)] : []))

  return (
    <motion.article
      variants={routeRise}
      onAnimationComplete={(definition) => {
        if (definition === 'show') setTimeout(() => setMerged(true), MERGE_AFTER_MS)
      }}
      className={cn(
        'relative overflow-hidden rounded-3xl border transition-[border-color,box-shadow,background-color,opacity] duration-500 sm:col-span-2',
        merged ? 'bg-card' : 'border-transparent bg-transparent shadow-none',
        merged && (picked
          ? 'border-primary shadow-[0_0_0_3px_rgba(173,239,129,0.7),0_24px_56px_-28px_rgba(84,160,40,0.7)]'
          : 'border-border shadow-[0_24px_60px_-34px_rgba(15,23,42,0.5)]'),
        dimmed && 'opacity-60',
      )}
    >
      <div className="relative h-44 sm:h-52">
        <motion.div className="absolute inset-0 flex" initial={false} animate={{ gap: merged ? 0 : 14 }} transition={SPRING}>
          {card.stops.map((stop, i) => (
            <motion.div
              key={stop.id}
              initial={false}
              animate={merged ? { borderRadius: 0, rotate: 0, scale: 1 } : { borderRadius: 24, rotate: i % 2 ? 1.6 : -1.6, scale: 0.95 }}
              transition={{ ...SPRING, delay: merged ? i * 0.04 : 0 }}
              className="relative min-w-0 flex-1 overflow-hidden shadow-[0_18px_40px_-26px_rgba(15,23,42,0.6)]"
            >
              <TripArt kind={scenes[i]} seed={stop.id} still className="absolute inset-0" />
              <span className="absolute inset-0 bg-linear-to-t from-slate-950/70 via-slate-950/10 to-transparent" />
              <div className="absolute right-3 bottom-3 left-3 sm:right-4 sm:left-4">
                <span className="mb-1.5 inline-flex rounded-full bg-white/90 px-2 py-0.5 text-[11px] font-semibold text-foreground">
                  {stop.nights} {plural(stop.nights, ['ночь', 'ночи', 'ночей'])}
                  {stop.day !== null && <span className="ml-1.5 font-medium text-muted-foreground">{temp(stop.day)}</span>}
                </span>
                <h3 className="m-0 truncate text-lg leading-tight font-semibold text-white sm:text-[22px]">{stop.name}</h3>
                <p className="m-0 mt-0.5 truncate text-[12px] font-medium text-white/85">
                  <span className="mr-1">{flagEmoji(stop.country_code)}</span>
                  {stop.country}
                </p>
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* the joints: how you get from one city to the next, popping in once the cards close up */}
        {between.map((leg, i) => (
          <motion.span
            key={`${leg.from}-${leg.to}`}
            initial={false}
            animate={merged ? { scale: 1, opacity: 1 } : { scale: 0.4, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 420, damping: 22, delay: merged ? 0.25 + i * 0.08 : 0 }}
            style={{ left: `${((i + 1) / card.stops.length) * 100}%` }}
            className="absolute top-[38%] z-10 flex -translate-x-1/2 items-center gap-1 rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap text-foreground shadow-md"
          >
            <ModeIcon mode={leg.mode} className={cn('h-3.5 w-3.5', leg.mode === 'flight' ? 'text-highlight' : 'text-[#3f7d22]')} />
            {hours(leg.ticket?.hours || leg.hours)}
          </motion.span>
        ))}

        <motion.div
          initial={false}
          animate={{ opacity: merged ? 1 : 0, y: merged ? 0 : -6 }}
          transition={{ ...SPRING, delay: merged ? 0.15 : 0 }}
          className="absolute inset-x-3 top-3 z-10 flex items-start justify-between gap-2"
        >
          <span className="flex flex-wrap gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-full bg-highlight px-2.5 py-1 text-[11px] font-semibold text-white shadow-md">
              <ModeIcon mode="flight" className="h-3 w-3" />
              Маршрут · {card.stops.length} {plural(card.stops.length, ['город', 'города', 'городов'])} · {nights}{' '}
              {plural(nights, ['ночь', 'ночи', 'ночей'])}
            </span>
            {best && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground shadow-md">
                <SparklesIcon className="h-3.5 w-3.5" aria-hidden />
                Лучшее совпадение
              </span>
            )}
          </span>
          <MatchRing value={card.match} on={merged} />
        </motion.div>
      </div>

      <motion.div
        initial={false}
        animate={{ opacity: merged ? 1 : 0, y: merged ? 0 : -10 }}
        transition={{ ...SPRING, delay: merged ? 0.2 : 0 }}
        className="flex flex-col gap-3 p-4 sm:p-5"
      >
        <p className="m-0 text-[14px] leading-relaxed text-foreground">{card.why}</p>

        <ul className="m-0 flex list-none flex-wrap items-center gap-1.5 p-0" aria-label="Интересы">
          {card.interests.map((it) => (
            <li
              key={it.kind}
              className={cn(
                'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12px] font-medium',
                it.covered ? 'bg-accent text-foreground' : 'bg-secondary text-faint',
              )}
            >
              {it.covered ? <CheckIcon className="h-3.5 w-3.5 text-[#4c9a2a]" aria-hidden /> : <MinusIcon className="h-3.5 w-3.5" aria-hidden />}
              {it.label}
            </li>
          ))}
        </ul>

        <ol className="m-0 -mx-2 flex flex-col p-0" aria-label="Плечи маршрута">
          {card.legs.map((leg, i) => (
            <LegRow key={`${i}-${leg.from}-${leg.to}`} leg={leg} index={i} />
          ))}
        </ol>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-inset px-4 py-3">
          <div>
            <p className="m-0 text-[12px] text-muted-foreground">
              Билеты на весь маршрут, на человека
            </p>
            <p className="m-0 text-lg font-semibold text-foreground tabular-nums">
              {card.total_rub ? `от ${formatRub(card.total_rub)}` : 'цены уточню'}
              {card.total_rub && !card.total_complete && (
                <span className="ml-2 text-[12px] font-normal text-muted-foreground">без плеч, где билетов пока нет</span>
              )}
            </p>
            {flightDays.length > 1 && (
              <p className={cn('m-0 mt-0.5 flex items-center gap-1 text-[12px]', card.dates_chained ? 'text-[#3f7d22]' : 'text-amber-600')}>
                {card.dates_chained ? <CheckIcon className="h-3.5 w-3.5" aria-hidden /> : <MinusIcon className="h-3.5 w-3.5" aria-hidden />}
                {card.dates_chained
                  ? `Даты состыкованы: ${flightDays.join(' → ')}`
                  : 'Самые дешёвые даты не стыкуются, соберу точнее при бронировании'}
              </p>
            )}
          </div>
          <ul className="m-0 flex list-none flex-wrap gap-x-3 gap-y-1 p-0 text-[12px]">
            {countries.map((s) => (
              <li key={s.country} className="flex items-center gap-1 text-foreground">
                {s.visa_easy ? (
                  <CheckBadgeIcon className="h-4 w-4 text-[#4c9a2a]" aria-hidden />
                ) : (
                  <IdentificationIcon className="h-4 w-4 text-amber-500" aria-hidden />
                )}
                {s.country}: {s.visa}
              </li>
            ))}
          </ul>
        </div>

        {card.tradeoff && (
          <p className="m-0 flex items-start gap-2 rounded-xl bg-secondary px-3 py-2 text-[13px] leading-snug text-secondary-foreground">
            <MinusIcon className="mt-0.5 h-4 w-4 shrink-0 text-faint" aria-hidden />
            {card.tradeoff}
          </p>
        )}

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 260, damping: 30 }}
              className="overflow-hidden"
            >
              <div className="grid gap-3 pt-1 sm:grid-cols-3">
                {card.stops.map((s) => (
                  <div key={s.id}>
                    <p className="m-0 text-[13px] font-semibold text-foreground">{s.name}</p>
                    <ul className="m-0 mt-1 flex list-disc flex-col gap-0.5 pl-4 text-[13px] text-muted-foreground">
                      {s.highlights.map((h) => (
                        <li key={h}>{h}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-1 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="inline-flex h-10 items-center gap-1 rounded-full px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            {open ? 'Свернуть' : 'Что посмотреть'}
            <ChevronDownIcon className={cn('h-4 w-4 transition-transform duration-300', open && 'rotate-180')} aria-hidden />
          </button>
          <span className="hidden text-[12px] text-faint sm:inline">{card.kids}</span>
          <motion.button
            type="button"
            onClick={onPick}
            disabled={!canPick && !picked}
            whileTap={canPick ? { scale: 0.96 } : undefined}
            className={cn(
              'ml-auto inline-flex h-10 items-center gap-1.5 rounded-full px-5 text-sm font-semibold transition-colors',
              picked
                ? 'bg-foreground text-white'
                : 'bg-primary text-primary-foreground hover:bg-primary-hover disabled:bg-secondary disabled:text-faint',
            )}
          >
            {picked && <CheckIcon className="h-4 w-4" aria-hidden />}
            {picked ? 'Выбрано' : 'Выбрать маршрут'}
          </motion.button>
        </div>
      </motion.div>
    </motion.article>
  )
}
