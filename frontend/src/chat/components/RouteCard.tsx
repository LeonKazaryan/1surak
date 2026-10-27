import { useContext, useState } from 'react'
import { motion, type Variants } from 'motion/react'
import { CheckIcon, ChevronRightIcon, MinusIcon, SparklesIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { RouteCard as Route, RouteLeg } from '@/types/api'
import { CurrencyContext, flagEmoji, formatMoney, keepPricesTogether, plural } from '../widgets'
import { CountUp } from './CountUp'
import { Credit } from './Credit'
import { creditsOf, KIND_COLOR, legKind, saving, travelDays, units } from './legFormat'
import { ModeIcon } from './LegRow'
import { PriceChangeNote } from './ticket'
import { sceneKinds } from './routeScenes'
import { hours, temp } from './ticketFormat'
import { TripArt } from './TripArt'
import { VisaChip } from './VisaChip'

const SPRING = { type: 'spring', stiffness: 230, damping: 26 } as const
const MERGE_AFTER_MS = 140 // the stop cards land first, then close up into one route
const DENSE_FROM = 4 // cities in the banner from which the panels get narrow and the text small
const TIGHT_FROM = 6
const NO_VISA = new Set(['none', 'visa_free'])

/** The route rises like any card, but as separate city cards: they merge once it has landed. */
const routeRise: Variants = {
  hidden: { opacity: 0, y: 32 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 220, damping: 24 } },
}

/** How well the route covers what the user wants, as a ring that fills in once the card is whole. */
function MatchRing({ value, on }: { value: number; on: boolean }) {
  return (
    <span className="flex shrink-0 items-center gap-2 rounded-full bg-white/90 p-1 shadow-sm backdrop-blur sm:pr-3" title="Совпадение с интересами">
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
      <span className="hidden text-[12px] leading-tight font-medium text-foreground sm:block">
        совпадение
        <br />
        <span className="text-muted-foreground">с интересами</span>
      </span>
    </span>
  )
}

/** What the whole route costs in tickets, what the trains and the smarter ways saved, and whether the dates
 * follow one another. */
export function RouteTotal({ card }: { card: Route }) {
  const currency = useContext(CurrencyContext)
  const days = travelDays(card.legs)
  const saved = card.legs.reduce((sum, leg) => sum + (saving(leg) ?? 0), 0)
  const byLand = card.legs
    .flatMap(units)
    .reduce((sum, part) => sum + (part.mode === 'ground' ? (part.ground?.price_rub ?? 0) : 0), 0)
  return (
    <div className="rounded-2xl bg-inset px-4 py-3">
      <p className="m-0 text-[12px] text-muted-foreground">Билеты на весь маршрут, на человека</p>
      <p className="m-0 text-lg font-semibold text-foreground tabular-nums">
        {card.total_rub ? (
          <>
            от <CountUp value={card.total_rub} format={(n) => formatMoney(n, currency)} />
          </>
        ) : (
          'цены уточню'
        )}
        {card.total_rub && !card.total_complete && (
          <span className="ml-2 text-[12px] font-normal text-muted-foreground">без плеч, где билетов пока нет</span>
        )}
      </p>
      {byLand > 0 && (
        <p className="m-0 text-[12px] text-muted-foreground">в том числе поезда и автобусы на {formatMoney(byLand, currency)}</p>
      )}
      {card.price_change && <PriceChangeNote change={card.price_change} className="block" />}
      {saved > 0 && (
        <motion.p
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...SPRING, delay: 0.6 }}
          className="m-0 mt-0.5 flex items-center gap-1 text-[12px] font-medium text-[#3f7d22]"
        >
          <SparklesIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
          {`Умные пересадки сберегли ${formatMoney(saved, currency)} против рейсов с пересадками`}
        </motion.p>
      )}
      {days.length > 1 && (
        <p className={cn('m-0 mt-0.5 flex items-center gap-1 text-[12px]', card.dates_chained ? 'text-[#3f7d22]' : 'text-amber-600')}>
          {card.dates_chained ? <CheckIcon className="h-3.5 w-3.5 shrink-0" aria-hidden /> : <MinusIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />}
          {card.dates_chained
            ? `Даты состыкованы: ${days.join(' → ')}`
            : 'Самые дешёвые даты не стыкуются, соберу точнее при бронировании'}
        </p>
      )}
    </div>
  )
}

/** A joint of the banner: how you get from one city to the next. A smarter way shows each of its means and
 * a green ring. */
function Seam({ leg, at, order, merged, tight }: { leg: RouteLeg; at: number; order: number; merged: boolean; tight: boolean }) {
  const kinds = [...new Set(units(leg).map(legKind))]
  const smart = Boolean(leg.parts?.length)
  return (
    <motion.span
      initial={false}
      animate={merged ? { scale: 1, opacity: 1 } : { scale: 0.4, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 420, damping: 22, delay: merged ? 0.25 + order * 0.08 : 0 }}
      style={{ left: `${at * 100}%` }}
      title={smart ? `Умный путь через ${leg.via}` : undefined}
      className={cn(
        'absolute top-[38%] z-10 flex -translate-x-1/2 items-center gap-1 rounded-full bg-white py-1 text-[11px] font-semibold whitespace-nowrap text-foreground shadow-md',
        tight ? 'px-1.5' : 'px-2.5',
        smart && 'ring-2 ring-primary',
      )}
    >
      {kinds.map((kind) => (
        <ModeIcon key={kind} mode={kind} className={cn('h-3.5 w-3.5', KIND_COLOR[kind])} />
      ))}
      <span className={cn(tight && 'hidden sm:inline')}>{hours(leg.ticket?.hours || leg.hours)}</span>
    </motion.span>
  )
}

/** Where a seam sits along the banner: between the city a leg leaves and the one it reaches. */
function seamAt(leg: RouteLeg, index: number, stops: number): number | null {
  if (leg.from_stop === undefined || leg.to_stop === undefined) return index > 0 && index < stops ? index / stops : null
  if (leg.from_stop === null || leg.to_stop === null) return null // home → first and last → home are not seams
  return (Math.min(leg.from_stop, leg.to_stop) + 1) / stops
}

interface RouteCardProps {
  card: Route
  best: boolean
  picked: boolean
  dimmed: boolean
  canPick: boolean
  onPick: () => void
  detailsOpen: boolean
  onDetails: () => void
  lit?: boolean
  onHover?: (on: boolean) => void
}

/** A multi-city route across two cells of the grid: its cities arrive as separate cards and merge into one. */
export function RouteCardView({ card, best, picked, dimmed, canPick, onPick, detailsOpen, onDetails, lit, onHover }: RouteCardProps) {
  const [merged, setMerged] = useState(false)
  const seams = card.legs.flatMap((leg, i) => {
    const at = seamAt(leg, i, card.stops.length)
    return at === null ? [] : [{ leg, at }]
  })
  const nights = card.stops.reduce((sum, s) => sum + s.nights, 0)
  const scenes = sceneKinds(card.stops)
  // a country that needs a visa (or an e-visa, a permit) gets its chip; one with no visa needs no words
  const visas = [...new Map(card.stops.filter((s) => s.visa_info && !NO_VISA.has(s.visa_info.rule)).map((s) => [s.country, s])).values()]
  const dense = card.stops.length >= DENSE_FROM
  const tight = card.stops.length >= TIGHT_FROM

  return (
    <motion.article
      id={`card-${card.id}`}
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
      variants={routeRise}
      onAnimationComplete={(definition) => {
        if (definition === 'show') setTimeout(() => setMerged(true), MERGE_AFTER_MS)
      }}
      className={cn(
        'relative scroll-mt-20 overflow-hidden rounded-3xl border transition-[border-color,box-shadow,background-color,opacity] duration-500 sm:col-span-2',
        merged ? 'bg-card' : 'border-transparent bg-transparent shadow-none',
        merged && (picked
          ? 'border-primary shadow-[0_0_0_3px_rgba(173,239,129,0.7)]'
          : cn(
              'shadow-[0_8px_24px_-18px_rgba(15,23,42,0.25)] hover:border-faintest',
              detailsOpen ? 'border-faintest' : 'border-border',
              lit && 'border-primary shadow-[0_0_0_3px_rgba(173,239,129,0.55)]',
            )),
        dimmed && 'opacity-60',
      )}
    >
      <div className="relative h-44 sm:h-52">
        <motion.div className="absolute inset-0 flex" initial={false} animate={{ gap: merged ? 0 : dense ? 8 : 14 }} transition={SPRING}>
          {card.stops.map((stop, i) => (
            <motion.div
              key={stop.id}
              initial={false}
              animate={merged ? { borderRadius: 0, rotate: 0, scale: 1 } : { borderRadius: dense ? 18 : 24, rotate: i % 2 ? 1.6 : -1.6, scale: 0.95 }}
              transition={{ ...SPRING, delay: merged ? i * 0.04 : 0 }}
              className="relative min-w-0 flex-1 overflow-hidden shadow-[0_8px_24px_-18px_rgba(15,23,42,0.35)]"
            >
              <TripArt kind={scenes[i]} seed={stop.id} photo={stop.photo} still className="absolute inset-0" />
              <span className="pointer-events-none absolute inset-0 bg-linear-to-t from-slate-950/70 via-slate-950/10 to-transparent" />
              <div className={cn('absolute bottom-3', dense ? 'right-2 left-2 sm:right-3 sm:left-3' : 'right-3 left-3 sm:right-4 sm:left-4')}>
                <span
                  className={cn(
                    'mb-1.5 inline-flex rounded-full bg-white/90 font-semibold text-foreground',
                    dense ? 'px-1.5 py-0.5 text-[10px] sm:text-[11px]' : 'px-2 py-0.5 text-[11px]',
                  )}
                >
                  {stop.nights}
                  {tight ? <span className="sm:hidden">&nbsp;н.</span> : null}
                  <span className={cn(tight && 'hidden sm:inline')}>&nbsp;{plural(stop.nights, ['ночь', 'ночи', 'ночей'])}</span>
                  {stop.day !== null && (
                    <span className={cn('ml-1.5 font-medium text-muted-foreground', dense && 'hidden sm:inline')}>{temp(stop.day)}</span>
                  )}
                </span>
                <h3
                  className={cn(
                    'm-0 leading-tight font-semibold text-white',
                    dense ? 'line-clamp-2 text-[13px] break-words hyphens-auto sm:text-base' : 'truncate text-lg sm:text-[22px]',
                  )}
                >
                  {stop.name}
                </h3>
                <p className={cn('m-0 mt-0.5 truncate font-medium text-white/85', dense ? 'text-[11px]' : 'text-[12px]')}>
                  <span className={cn(!dense && 'mr-1')}>{flagEmoji(stop.country_code)}</span>
                  <span className={cn(dense && 'hidden sm:inline sm:pl-1')}>{stop.country}</span>
                </p>
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* the joints: how you get from one city to the next, popping in once the cards close up */}
        {seams.map(({ leg, at }, i) => (
          <Seam key={`${leg.from}-${leg.to}`} leg={leg} at={at} order={i} merged={merged} tight={tight} />
        ))}

        <motion.div
          initial={false}
          animate={{ opacity: merged ? 1 : 0, y: merged ? 0 : -6 }}
          transition={{ ...SPRING, delay: merged ? 0.15 : 0 }}
          className="absolute inset-x-3 top-3 z-10 flex items-start justify-between gap-2"
        >
          <span className="flex flex-wrap gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-full bg-highlight px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap text-white shadow-md">
              <ModeIcon mode="flight" className="h-3 w-3" />
              <span className="hidden sm:inline">Маршрут ·</span> {card.stops.length} {plural(card.stops.length, ['город', 'города', 'городов'])} · {nights}{' '}
              {plural(nights, ['ночь', 'ночи', 'ночей'])}
            </span>
            {best && (
              <span className="rounded-full bg-primary px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap text-primary-foreground shadow-md">
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
        <p className="m-0 text-[14px] leading-relaxed text-foreground">{keepPricesTogether(card.why)}</p>

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

        {visas.length > 0 && (
          <ul className="m-0 flex list-none flex-wrap items-center gap-1.5 p-0" aria-label="Визы">
            {visas.map((stop) => (
              <VisaChip key={stop.country} info={stop.visa_info!} prefix={`${stop.country}: `} />
            ))}
          </ul>
        )}

        <div>
          <RouteTotal card={card} />
          {creditsOf(card.legs).map((credit) => (
            <Credit key={credit.text} credit={credit} className="mt-1.5 px-1" />
          ))}
        </div>

        {card.tradeoff && (
          <p className="m-0 flex items-start gap-2 rounded-xl bg-secondary px-3 py-2 text-[13px] leading-snug text-secondary-foreground">
            <MinusIcon className="mt-0.5 h-4 w-4 shrink-0 text-faint" aria-hidden />
            {keepPricesTogether(card.tradeoff)}
          </p>
        )}

        <div className="mt-1 flex items-center gap-2">
          <button
            type="button"
            onClick={onDetails}
            aria-expanded={detailsOpen}
            className={cn(
              'inline-flex h-10 items-center gap-1 rounded-full px-3 text-[13px] font-medium transition-colors hover:bg-secondary hover:text-foreground',
              detailsOpen ? 'bg-secondary text-foreground' : 'text-muted-foreground',
            )}
          >
            Подробнее
            <ChevronRightIcon className="h-4 w-4" aria-hidden />
          </button>
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
