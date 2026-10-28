import { useCallback, useContext, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowTopRightOnSquareIcon, CheckBadgeIcon, IdentificationIcon, NoSymbolIcon } from '@heroicons/react/20/solid'
import { fetchVisa } from '@/api/client'
import { cn } from '@/components/ui/utils'
import type { VisaFee, VisaInfo } from '@/types/api'
import { CurrencyContext, formatMoney } from '../widgets'
import { shortDate } from './ticketFormat'

const PAID = new Set<VisaInfo['rule']>(['on_arrival', 'eta', 'evisa', 'visa_required'])
const WIDTH = 296
const GAP = 8
const CLOSE_MS = 140

// one request per pair for the whole page: three cards of the USA ask once
const asked = new Map<string, Promise<VisaFee | null>>()

function feeFor(pair: string): Promise<VisaFee | null> {
  let found = asked.get(pair)
  if (!found) {
    found = fetchVisa(pair).then((info) => info.fee ?? null)
    found.catch(() => asked.delete(pair)) // a failure is asked again on the next hover
    asked.set(pair, found)
  }
  return found
}

/** «185 $», «135 £», «бесплатно»: the fee in the currency the source names. */
function feeText(fee: VisaFee): string {
  if (fee.amount === 0) return 'бесплатно'
  try {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: fee.currency,
      maximumFractionDigits: Number.isInteger(fee.amount) ? 0 : 2,
    }).format(fee.amount)
  } catch {
    return `${fee.amount} ${fee.currency}`
  }
}

type Tone = 'good' | 'easy' | 'hard' | 'closed'

function toneOf(rule: VisaInfo['rule']): Tone {
  if (rule === 'none' || rule === 'visa_free') return 'good'
  if (rule === 'no_admission') return 'closed'
  return rule === 'visa_required' ? 'hard' : 'easy'
}

const CHIP: Record<Tone, string> = {
  good: 'bg-accent text-foreground',
  easy: 'bg-amber-50 text-amber-900',
  hard: 'bg-amber-100 font-semibold text-amber-950 ring-1 ring-amber-300/70',
  closed: 'bg-danger-soft font-semibold text-danger',
}
const ICON_TONE: Record<Tone, string> = {
  good: 'text-[#4c9a2a]',
  easy: 'text-amber-500',
  hard: 'text-amber-600',
  closed: 'text-danger',
}

function ToneIcon({ tone, className }: { tone: Tone; className?: string }) {
  const Icon = tone === 'good' ? CheckBadgeIcon : tone === 'closed' ? NoSymbolIcon : IdentificationIcon
  return <Icon aria-hidden className={cn('h-4 w-4 shrink-0', ICON_TONE[tone], className)} />
}

type FeeState = { status: 'idle' } | { status: 'loading' } | { status: 'failed' } | { status: 'done'; fee: VisaFee | null }

function FeeBlock({ state }: { state: FeeState }) {
  const currency = useContext(CurrencyContext)
  if (state.status === 'idle') return null
  if (state.status === 'loading') {
    return (
      <div className="mt-2.5 rounded-xl bg-inset px-3 py-2.5">
        <span className="text-shimmer text-[12px] font-medium">Ищу стоимость в открытых источниках…</span>
      </div>
    )
  }
  if (state.status === 'failed' || !state.fee) {
    return (
      <p className="m-0 mt-2.5 rounded-xl bg-inset px-3 py-2 text-[12px] leading-snug text-muted-foreground">
        {state.status === 'failed'
          ? 'Не получилось узнать стоимость, наведите ещё раз чуть позже.'
          : 'Стоимость не нашлась в открытых источниках, её назовут в консульстве или визовом центре.'}
      </p>
    )
  }
  const fee = state.fee
  const local = fee.rub !== null && fee.amount > 0 && fee.currency !== currency.code ? formatMoney(fee.rub, currency) : null
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 320, damping: 26 }}
      className="mt-2.5 rounded-xl bg-amber-50 px-3 py-2"
    >
      <p className="m-0 text-[12px] text-amber-900/80">{fee.amount === 0 ? 'Сбор' : 'Стоимость около'}</p>
      <p className="m-0 flex flex-wrap items-baseline gap-x-2 text-[18px] leading-tight font-semibold text-foreground tabular-nums">
        {feeText(fee)}
        {local && <span className="text-[13px] font-medium text-muted-foreground">≈ {local}</span>}
      </p>
      <p className="m-0 mt-0.5 text-[12px] leading-snug text-muted-foreground">{fee.covers}</p>
      <a
        href={fee.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 inline-flex items-center gap-1 text-[12px] font-medium text-highlight underline-offset-2 hover:underline"
      >
        {fee.source}
        <span className="font-normal text-faint">· проверено {shortDate(fee.checked)}</span>
        <ArrowTopRightOnSquareIcon className="h-3 w-3" aria-hidden />
      </a>
    </motion.div>
  )
}

interface VisaChipProps {
  info: VisaInfo
  /** «Грузия: » in a list of countries. */
  prefix?: string
}

/** The visa as a chip; pointing at it (or a tap) tells what the traveller's passport needs and what it costs,
 * the fee found on the web once and asked for only when someone looks. */
export function VisaChip({ info, prefix }: VisaChipProps) {
  const id = useId()
  const tone = toneOf(info.rule)
  const paid = PAID.has(info.rule)
  const trigger = useRef<HTMLButtonElement>(null)
  const popover = useRef<HTMLDivElement>(null)
  const closing = useRef<number | undefined>(undefined)
  const [open, setOpen] = useState(false)
  const [place, setPlace] = useState<{ left: number; top?: number; bottom?: number }>({ left: 0 })
  const [fee, setFee] = useState<FeeState>(info.fee ? { status: 'done', fee: info.fee } : { status: 'idle' })

  const measure = useCallback(() => {
    const box = trigger.current?.getBoundingClientRect()
    if (!box) return
    const left = Math.min(Math.max(GAP, box.left + box.width / 2 - WIDTH / 2), window.innerWidth - WIDTH - GAP)
    setPlace(box.top > 260 ? { left, bottom: window.innerHeight - box.top + GAP } : { left, top: box.bottom + GAP })
  }, [])

  const show = () => {
    window.clearTimeout(closing.current)
    measure()
    setOpen(true)
    if (paid && (fee.status === 'idle' || fee.status === 'failed')) {
      setFee({ status: 'loading' })
      feeFor(info.pair).then(
        (found) => setFee({ status: 'done', fee: found }),
        () => setFee({ status: 'failed' }),
      )
    }
  }
  const hide = () => {
    window.clearTimeout(closing.current)
    closing.current = window.setTimeout(() => setOpen(false), CLOSE_MS)
  }

  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => {
      const target = e.target as Node
      if (!trigger.current?.contains(target) && !popover.current?.contains(target)) setOpen(false)
    }
    const key = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)
    window.addEventListener('pointerdown', away)
    window.addEventListener('keydown', key)
    return () => {
      window.removeEventListener('scroll', measure, true)
      window.removeEventListener('resize', measure)
      window.removeEventListener('pointerdown', away)
      window.removeEventListener('keydown', key)
    }
  }, [open, measure])

  useEffect(() => () => window.clearTimeout(closing.current), [])

  const above = place.bottom !== undefined
  return (
    <li className="min-w-0 list-none">
      <button
        ref={trigger}
        type="button"
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={show}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        className={cn(
          'inline-flex max-w-full min-w-0 cursor-help items-center gap-1.5 rounded-full py-0.5 pr-2.5 pl-1.5 text-[13px] transition-[box-shadow,filter] hover:brightness-[0.98] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
          CHIP[tone],
        )}
      >
        <ToneIcon tone={tone} />
        <span className="truncate">
          {prefix}
          {info.label}
        </span>
      </button>
      {createPortal(
        <AnimatePresence>
          {open && (
            <motion.div
              ref={popover}
              id={id}
              role="tooltip"
              onMouseEnter={show}
              onMouseLeave={hide}
              initial={{ opacity: 0, y: above ? 6 : -6, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: above ? 4 : -4, scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 420, damping: 30 }}
              style={{ position: 'fixed', left: place.left, top: place.top, bottom: place.bottom, width: WIDTH }}
              className={cn(
                'z-50 rounded-2xl border border-border bg-card p-3.5 text-left shadow-[0_18px_44px_-18px_rgba(15,23,42,0.4)]',
                above ? 'origin-bottom' : 'origin-top',
              )}
            >
              <p className="m-0 flex items-center gap-1.5 text-[13px] font-semibold text-foreground">
                <ToneIcon tone={tone} />
                {prefix}
                {info.label}
              </p>
              {info.countries && info.countries.length > 1 && (
                <ul className="m-0 mt-2 flex list-none flex-wrap gap-1 p-0" aria-label="Одна виза на страны">
                  {info.countries.map((name) => (
                    <li key={name} className="rounded-full bg-inset px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                      {name}
                    </li>
                  ))}
                </ul>
              )}
              <p className="m-0 mt-1.5 text-[13px] leading-snug text-foreground">{info.text}</p>
              {info.also && info.also.length > 0 && (
                <ul className="m-0 mt-2 flex list-none flex-col gap-1 rounded-xl bg-accent/60 p-2 px-2.5" aria-label="По этой визе пускают">
                  {info.also.map((place) => (
                    <li key={place.name} className="flex items-center gap-1.5 text-[12px] text-foreground">
                      <CheckBadgeIcon aria-hidden className="h-3.5 w-3.5 shrink-0 text-[#4c9a2a]" />
                      <span className="font-medium">{place.name}</span>
                      {place.days && <span className="text-muted-foreground">до {place.days} дн.</span>}
                      <a
                        href={place.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-auto inline-flex items-center gap-0.5 text-[11px] text-highlight underline-offset-2 hover:underline"
                      >
                        {place.source}
                        <ArrowTopRightOnSquareIcon className="h-3 w-3" aria-hidden />
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              {paid && <FeeBlock state={fee} />}
              <p className="m-0 mt-2 text-[11px] leading-snug text-faint">Паспорт считаю по стране вылета, правила по Passport Index</p>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </li>
  )
}
