import { useState } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import {
  CheckBadgeIcon,
  CheckIcon,
  ChevronDownIcon,
  ExclamationTriangleIcon,
  FaceSmileIcon,
  IdentificationIcon,
  MinusIcon,
  PaperAirplaneIcon,
  PlusIcon,
  SparklesIcon,
  SunIcon,
} from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { DestinationCard, DestinationsEvent } from '@/types/api'
import { flagEmoji } from '../widgets'
import { TripArt } from './TripArt'

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

function hours(value: number): string {
  return `${value.toLocaleString('ru-RU')} ч`
}

function temp(value: number): string {
  return `${value > 0 ? '+' : ''}${value}°`
}

function travelText(card: DestinationCard): string | null {
  if (card.flight_hours) return `${hours(card.flight_hours)} · ${card.direct ? 'прямой' : 'с пересадкой'}`
  if (card.train_hours) return `поезд ${hours(card.train_hours)}`
  return null
}

function Fact({ icon: Icon, children, tone = 'default' }: { icon: typeof SunIcon; children: string; tone?: 'default' | 'good' | 'warn' }) {
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

function PriceLevel({ level, label }: { level: number; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px] text-foreground">
      <span className="flex text-[13px] font-bold" aria-hidden>
        {[1, 2, 3].map((n) => (
          <span key={n} className={n <= level ? 'text-highlight' : 'text-faintest'}>
            ₽
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
}

function Card({ card, best, picked, dimmed, canPick, onPick }: CardProps) {
  const [open, setOpen] = useState(false)
  const travel = travelText(card)
  const kind = card.kinds[0] ?? 'sea'

  return (
    <motion.article
      variants={rise}
      layout
      whileHover={{ y: -6 }}
      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-3xl border bg-card transition-[box-shadow,border-color,opacity] duration-300',
        picked
          ? 'border-primary shadow-[0_0_0_3px_rgba(173,239,129,0.7),0_24px_56px_-28px_rgba(84,160,40,0.7)]'
          : 'border-border shadow-[0_20px_50px_-32px_rgba(15,23,42,0.45)] hover:shadow-[0_28px_60px_-28px_rgba(15,23,42,0.45)]',
        dimmed && 'opacity-60',
      )}
    >
      <div className="relative h-40 overflow-hidden">
        <TripArt kind={kind} seed={card.id} image={card.image} className="transition-transform duration-700 ease-out group-hover:scale-[1.07]" />
        <div className="absolute inset-0 bg-linear-to-t from-slate-950/60 via-slate-950/10 to-transparent" />
        {best && (
          <motion.span
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 }}
            className="absolute top-3 left-3 inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-1 text-[11px] font-semibold text-primary-foreground shadow-md"
          >
            <SparklesIcon className="h-3.5 w-3.5" aria-hidden />
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
            {card.climate && <span className="text-white/70"> · погода в {card.climate.month_in}</span>}
          </p>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <p className="m-0 text-[14px] leading-relaxed text-foreground">{card.why}</p>
        <ul className="m-0 grid list-none grid-cols-2 gap-x-3 gap-y-2 p-0">
          {travel && <Fact icon={PaperAirplaneIcon}>{travel}</Fact>}
          <Fact icon={card.visa_easy ? CheckBadgeIcon : IdentificationIcon} tone={card.visa_easy ? 'good' : 'warn'}>
            {card.visa}
          </Fact>
          <li>
            <PriceLevel level={card.price_level} label={card.price} />
          </li>
          <Fact icon={FaceSmileIcon} tone={card.kids_fit === 'poor' ? 'warn' : 'default'}>
            {card.kids}
          </Fact>
        </ul>
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
              <ul className="m-0 flex list-none flex-col gap-1.5 p-0 pt-1">
                {card.highlights.map((text) => (
                  <li key={text} className="flex items-start gap-2 text-[13px] text-foreground">
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary">
                      <PlusIcon className="h-3 w-3 text-primary-foreground" aria-hidden />
                    </span>
                    {text}
                  </li>
                ))}
                {card.watch_out.map((text) => (
                  <li key={text} className="flex items-start gap-2 text-[13px] text-muted-foreground">
                    <ExclamationTriangleIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
                    {text}
                  </li>
                ))}
              </ul>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-auto flex items-center gap-2 pt-1">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="inline-flex h-10 items-center gap-1 rounded-full px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            {open ? 'Свернуть' : 'Подробнее'}
            <ChevronDownIcon className={cn('h-4 w-4 transition-transform duration-300', open && 'rotate-180')} aria-hidden />
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
  onPick: (card: DestinationCard) => void
}

/** The agent's picks as cards: an illustration, the weather and facts, why it fits and what you give up. */
export function DestinationCards({ widget, canPick, onPick }: DestinationCardsProps) {
  const [picked, setPicked] = useState<string | null>(null)

  return (
    <motion.div variants={grid} initial="hidden" animate="show" className="mt-4 flex flex-col gap-4">
      {widget.summary.length > 0 && (
        <motion.ul variants={grid} className="m-0 flex list-none flex-wrap items-center gap-1.5 p-0" aria-label="Подбирал по">
          <motion.li variants={chip} className="mr-1 text-xs font-semibold tracking-wider text-faint uppercase">
            Подбирал по
          </motion.li>
          {widget.summary.map((text) => (
            <motion.li key={text} variants={chip} className="rounded-full bg-accent px-2.5 py-1 text-[12px] font-medium text-foreground">
              {text}
            </motion.li>
          ))}
        </motion.ul>
      )}
      <motion.div variants={grid} className="grid gap-4 sm:grid-cols-2">
        {widget.cards.map((card, i) => (
          <Card
            key={card.id}
            card={card}
            best={i === 0}
            picked={picked === card.id}
            dimmed={picked !== null && picked !== card.id}
            canPick={canPick && picked === null}
            onPick={() => {
              setPicked(card.id)
              onPick(card)
            }}
          />
        ))}
      </motion.div>
    </motion.div>
  )
}
