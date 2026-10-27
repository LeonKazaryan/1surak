import { useContext, useState } from 'react'
import { DataCredit } from '@/components/DataCredit'
import { motion, type Variants } from 'motion/react'
import {
  ArrowTopRightOnSquareIcon,
  CheckBadgeIcon,
  CheckIcon,
  ChevronRightIcon,
  FaceSmileIcon,
  IdentificationIcon,
  MinusIcon,
  PaperAirplaneIcon,
  SunIcon,
} from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { Currency, DestinationCard, DestinationsCard, DestinationsEvent, PriceChange, RouteFlight } from '@/types/api'
import { CurrencyContext, RUB, flagEmoji, formatMoney, keepPricesTogether } from '../widgets'
import { AirlineLogo, PriceChangeNote } from './ticket'
import { hours, shortDate, stopsText, temp, travelText } from './ticketFormat'
import { RouteCardView } from './RouteCard'
import { TripArt } from './TripArt'
import { TripMap, type MapPin, type MapRoute } from '../map/TripMap'
import { VisaChip } from './VisaChip'

const grid: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.2 } },
}
const rise: Variants = {
  hidden: { opacity: 0, y: 32, scale: 0.95, filter: 'blur(8px)' },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    filter: 'blur(0px)',
    transition: { type: 'spring', stiffness: 220, damping: 24 },
  },
}
const chip: Variants = {
  hidden: { opacity: 0, scale: 0.85 },
  show: { opacity: 1, scale: 1, transition: { type: 'spring', stiffness: 400, damping: 24 } },
}

/** The real ticket as a strip: airline, stops, time in the air, date, price; opens it on Aviasales. */
export function TicketStrip({ flight, change }: { flight: RouteFlight; change?: PriceChange }) {
  const currency = useContext(CurrencyContext)
  // the direct option only when it differs from the ticket above: same flight twice is noise
  const direct = flight.transfers > 0 ? flight.direct_option : null
  return (
    <div className="flex flex-col gap-1.5">
      <a
        href={flight.link}
        target="_blank"
        rel="noopener noreferrer"
        className="group/ticket flex items-center gap-3 rounded-2xl border border-border bg-inset px-3 py-2.5 transition-colors hover:border-highlight/30 hover:bg-accent/60"
      >
        <AirlineLogo ticket={flight} className="h-9 w-9 p-0.5" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-semibold text-foreground">{flight.airline_name}</span>
          <span className="block truncate text-[12px] text-muted-foreground">
            <span className={flight.transfers === 0 ? 'font-medium text-[#4c9a2a]' : undefined}>{stopsText(flight)}</span>
            {flight.hours > 0 && ` · ${hours(flight.hours)}`}
          </span>
        </span>
        <span className="shrink-0 text-right">
          <span className="block text-[11px] text-faint">{shortDate(flight.departure)}, от</span>
          <span className="block text-[15px] leading-tight font-semibold text-foreground tabular-nums">
            {formatMoney(flight.price_rub, currency)}
          </span>
        </span>
      </a>
      {change && <PriceChangeNote change={change} className="px-1" />}
      {direct && (
        <a
          href={direct.link}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-1 text-[12px] text-muted-foreground transition-colors hover:text-foreground"
        >
          <AirlineLogo ticket={direct} className="h-4 w-4" />
          <span className="truncate">
            Прямой рейс {direct.airline_name} от {formatMoney(direct.price_rub, currency)}
            {direct.hours > 0 && `, ${hours(direct.hours)}`}
          </span>
        </a>
      )}
    </div>
  )
}

/** No cached ticket: two tickets through the main airport if we found them, and the live search on Aviasales. */
export function NoCachedTicket({ card }: { card: DestinationCard }) {
  const currency = useContext(CurrencyContext)
  const via = card.flight_via
  return (
    <div className="flex flex-col gap-1.5 rounded-2xl border border-border px-3.5 py-2.5 text-[13px]">
      {via ? (
        <p className="m-0 text-foreground">
          <span className="font-semibold">{`${via.estimate ? '≈ ' : ''}от ${formatMoney(via.price_rub, currency)}`}</span>
          <span className="text-muted-foreground">{` с пересадкой в ${via.via_in ?? via.via}, два билета`}</span>
        </p>
      ) : (
        <p className="m-0 text-muted-foreground">В кэше Aviasales цены пока нет</p>
      )}
      {card.search_link && (
        <a
          href={card.search_link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 self-start font-medium text-highlight underline-offset-2 hover:underline"
        >
          Найти билеты на Aviasales
          <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" aria-hidden />
        </a>
      )}
    </div>
  )
}

export function Fact({ icon: Icon, children, tone = 'default' }: { icon: typeof SunIcon; children: string; tone?: 'default' | 'good' | 'warn' }) {
  return (
    <li className="flex min-w-0 items-center gap-1.5 text-[13px] text-foreground">
      <Icon
        aria-hidden
        className={cn('h-4 w-4 shrink-0', tone === 'good' ? 'text-[#4c9a2a]' : tone === 'warn' ? 'text-amber-500' : 'text-highlight')}
      />
      <span className="truncate">{children}</span>
    </li>
  )
}

export function PriceLevel({ level, label }: { level: number; label: string }) {
  const { glyph } = useContext(CurrencyContext)
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px] text-foreground">
      <span className="flex text-[13px] font-bold" aria-hidden>
        {[1, 2, 3].map((n) => (
          <span key={n} className={n <= level ? 'text-highlight' : 'text-faintest'}>
            {glyph}
          </span>
        ))}
      </span>
      {label}
    </span>
  )
}

interface CardProps {
  card: DestinationCard
  best: boolean
  picked: boolean
  dimmed: boolean
  canPick: boolean
  onPick: () => void
  detailsOpen: boolean
  onDetails: () => void
  /** Its pin on the map is pointed at: the card answers with a glow. */
  lit?: boolean
  onHover?: (on: boolean) => void
}

function Card({ card, best, picked, dimmed, canPick, onPick, detailsOpen, onDetails, withKids, wide, lit, onHover }: CardProps & { withKids: boolean; wide: boolean }) {
  const travel = travelText(card)
  const kind = card.kinds[0] ?? 'sea'

  return (
    <motion.article
      id={`card-${card.id}`}
      variants={rise}
      layout
      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
      whileHover={{ y: -3 }}
      className={cn(
        'group relative flex scroll-mt-20 flex-col overflow-hidden rounded-3xl border bg-card transition-[box-shadow,border-color,opacity] duration-300',
        wide && 'sm:col-span-2',
        picked
          ? 'border-primary shadow-[0_0_0_3px_rgba(173,239,129,0.7)]'
          : cn(
              'shadow-[0_8px_24px_-18px_rgba(15,23,42,0.25)] hover:border-faintest hover:shadow-[0_22px_44px_-26px_rgba(15,23,42,0.35)]',
              detailsOpen ? 'border-faintest' : 'border-border',
              lit && 'border-primary shadow-[0_0_0_3px_rgba(173,239,129,0.55)]',
            ),
        dimmed && 'opacity-60',
      )}
    >
      <div className="relative h-40 overflow-hidden">
        <TripArt kind={kind} seed={card.id} photo={card.photo} className="transition-transform duration-700 ease-out group-hover:scale-[1.04]" />
        <div className="pointer-events-none absolute inset-0 bg-linear-to-t from-slate-950/80 via-slate-950/25 to-transparent" />
        {best && (
          <motion.span
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 }}
            className="absolute top-3 left-3 rounded-full bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground shadow-md"
          >
            Лучшее совпадение
          </motion.span>
        )}
        {card.climate && (card.climate.day !== undefined || card.climate.sea !== undefined) && (
          <span className="absolute top-3 right-3 inline-flex items-center gap-2 rounded-full bg-white/85 px-2.5 py-1 text-[12px] font-semibold text-foreground shadow-sm backdrop-blur-md">
            {card.climate.day !== undefined && (
              <span className="inline-flex items-center gap-1">
                <SunIcon className="h-3.5 w-3.5 text-amber-500" aria-hidden />
                {temp(card.climate.day)}
              </span>
            )}
            {card.climate.sea !== undefined && (
              <span className="inline-flex items-center gap-1 text-highlight">
                <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" aria-hidden>
                  <path d="M2 8c2-2 4-2 6 0s4 2 6 0 3-1.5 4-1M2 13c2-2 4-2 6 0s4 2 6 0 3-1.5 4-1" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" />
                </svg>
                {temp(card.climate.sea)}
              </span>
            )}
          </span>
        )}
        <div className="absolute right-4 bottom-3 left-4">
          <h3 className="m-0 text-[22px] leading-tight font-semibold tracking-tight text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
            {card.name}
          </h3>
          <p className="m-0 mt-0.5 text-[13px] font-medium text-white/85">
            <span className="mr-1">{flagEmoji(card.country_code)}</span>
            {card.country}
          </p>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <p className="m-0 text-[14px] leading-relaxed text-foreground">{keepPricesTogether(card.why)}</p>
        {card.flight && <TicketStrip flight={card.flight} change={card.price_change} />}
        {!card.flight && (card.flight_via || card.search_link) && <NoCachedTicket card={card} />}
        {/* only what tells the places apart: the price level and kids live in «Подробнее» */}
        <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-2 p-0">
          {!card.flight && travel && <Fact icon={PaperAirplaneIcon}>{travel}</Fact>}
          {!card.flight && !travel && !card.search_link && (
            <Fact icon={PaperAirplaneIcon} tone="warn">
              билетов не нашлось
            </Fact>
          )}
          {card.visa_info ? (
            <VisaChip info={card.visa_info} />
          ) : (
            <Fact icon={card.visa_easy ? CheckBadgeIcon : IdentificationIcon} tone={card.visa_easy ? 'good' : 'warn'}>
              {card.visa}
            </Fact>
          )}
          {withKids && card.kids && (
            <Fact icon={FaceSmileIcon} tone={card.kids_fit === 'poor' ? 'warn' : 'default'}>
              {card.kids}
            </Fact>
          )}
        </ul>
        {card.tradeoff && (
          <p className="m-0 flex items-start gap-2 rounded-xl bg-secondary px-3 py-2 text-[13px] leading-snug text-secondary-foreground">
            <MinusIcon className="mt-0.5 h-4 w-4 shrink-0 text-faint" aria-hidden />
            {keepPricesTogether(card.tradeoff)}
          </p>
        )}

        <div className="mt-auto flex items-center gap-2 pt-1">
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
            {picked ? 'Выбрано' : 'Выбрать'}
          </motion.button>
        </div>
      </div>
    </motion.article>
  )
}

interface DestinationCardsProps {
  widget: DestinationsEvent
  canPick: boolean
  onPick: (card: DestinationsCard) => void
  detailsId?: string | null
  onDetails: (card: DestinationsCard, currency: Currency) => void
}

/** The agent's picks as cards: an illustration, the weather and facts, why it fits and what you give up. */
export function DestinationCards({ widget, canPick, onPick, detailsId = null, onDetails }: DestinationCardsProps) {
  const [picked, setPicked] = useState<string | null>(null)
  const currency = widget.currency ?? RUB
  // routes take a whole row, so an odd count of places leaves one alone: it widens instead of leaving a hole
  const places = widget.cards.filter((card) => card.type !== 'route')
  const lone = places.length % 2 === 1 ? places[places.length - 1].id : null
  // the map and the cards point at each other: a card under the mouse lights its arc, a pin its card
  const [active, setActive] = useState<string | null>(null)
  const pins: MapPin[] = places.flatMap((card) =>
    card.lat != null && card.lon != null
      ? [
          {
            id: card.id,
            name: card.name,
            lat: card.lat,
            lon: card.lon,
            countryCode: card.country_code,
            note: card.flight ? `от ${formatMoney(card.flight.price_rub, currency)}` : undefined,
          },
        ]
      : [],
  )
  const routes: MapRoute[] = widget.cards.flatMap((card) =>
    card.type === 'route' && card.stops.every((s) => s.lat != null && s.lon != null)
      ? [
          {
            id: card.id,
            stops: card.stops.map((s) => ({ name: s.name, lat: s.lat!, lon: s.lon! })),
            modes: card.legs.map((leg) => (leg.parts?.length ? 'flight' : leg.mode)),
          },
        ]
      : [],
  )

  return (
    <CurrencyContext value={currency}>
      <motion.div variants={grid} initial="hidden" animate="show" className="mt-4 flex flex-col gap-4">
        {(pins.length > 0 || routes.length > 0) && (
          <motion.div variants={chip}>
            <TripMap
              origin={widget.origin}
              pins={pins}
              routes={routes}
              active={active}
              onActive={setActive}
              onSelect={(id) => document.getElementById(`card-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
            />
          </motion.div>
        )}
        {/* a route spans two cells; dense flow lets single places fill the holes it leaves */}
        <motion.div variants={grid} className="grid gap-4 sm:grid-flow-row-dense sm:grid-cols-2">
          {widget.cards.map((card, i) => {
            const props = {
              best: i === 0,
              picked: picked === card.id,
              dimmed: picked !== null && picked !== card.id,
              canPick: canPick && picked === null,
              onPick: () => {
                setPicked(card.id)
                onPick(card)
              },
              detailsOpen: detailsId === card.id,
              onDetails: () => onDetails(card, currency),
              lit: active === card.id,
              onHover: (on: boolean) => setActive(on ? card.id : null),
            }
            return card.type === 'route' ? (
              <RouteCardView key={card.id} card={card} {...props} />
            ) : (
              <Card key={card.id} card={card} withKids={Boolean(widget.with_kids)} wide={card.id === lone} {...props} />
            )
          })}
        </motion.div>
        {widget.cards.some((card) => card.type !== 'route' && card.climate) && (
          <DataCredit sources={['openMeteo']} prefix="Погода:" className="mt-2" />
        )}
      </motion.div>
    </CurrencyContext>
  )
}
