import { motion } from 'motion/react'
import type { BookingEvent } from '@/types/api'
import { RUB, formatMoney } from '../widgets'
import { nightsText, spanText } from './planFormat'

// a burst of the palette's colours when the trip is booked: once, from behind the check
const CONFETTI = Array.from({ length: 16 }, (_, i) => {
  const angle = (i / 16) * Math.PI * 2 + (i % 2 ? 0.2 : -0.1)
  const reach = 46 + (i % 4) * 14
  return {
    x: Math.cos(angle) * reach,
    y: Math.sin(angle) * reach,
    color: ['var(--primary)', 'var(--highlight)', '#4c9a2a', '#f5c451'][i % 4],
    size: i % 3 ? 6 : 8,
    turn: (i % 2 ? 1 : -1) * (90 + i * 12),
  }
})

/** The simulated purchase, kept in the chat: the booking number, the trip, what was paid. It lands with a
 * stamp and a burst of confetti. */
export function BookingCard({ booking }: { booking: BookingEvent }) {
  const currency = booking.currency ?? RUB
  return (
    <motion.article
      aria-label={`Бронь ${booking.number}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 24 }}
      className="relative mt-3 flex items-start gap-4 overflow-hidden rounded-3xl border border-primary bg-accent p-4 sm:p-5"
    >
      <motion.span
        aria-hidden
        initial={{ opacity: 0, scale: 2.2, rotate: -24 }}
        animate={{ opacity: 1, scale: 1, rotate: -12 }}
        transition={{ type: 'spring', stiffness: 520, damping: 18, delay: 0.45 }}
        className="pointer-events-none absolute top-3 right-3 rounded-lg border-2 border-[#3f7d22]/70 px-2 py-0.5 text-[11px] font-bold tracking-[0.18em] text-[#3f7d22]/80 uppercase sm:top-4 sm:right-4"
      >
        Забронировано
      </motion.span>
      <span className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary">
        {CONFETTI.map((c, i) => (
          <motion.span
            key={i}
            aria-hidden
            className="absolute rounded-[2px]"
            style={{ width: c.size, height: c.size * 0.6, background: c.color }}
            initial={{ x: 0, y: 0, opacity: 0, rotate: 0 }}
            animate={{ x: c.x, y: c.y, opacity: [0, 1, 1, 0], rotate: c.turn }}
            transition={{ duration: 1.1, delay: 0.25, ease: [0.16, 1, 0.3, 1], times: [0, 0.1, 0.7, 1] }}
          />
        ))}
        <svg viewBox="0 0 24 24" className="relative h-6 w-6 text-primary-foreground" aria-hidden>
          <motion.path
            d="M5 12.5l4.5 4.5L19 7.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.15, ease: 'easeOut' }}
          />
        </svg>
      </span>
      <div className="min-w-0 flex-1">
        <p className="m-0 text-[12px] font-medium text-muted-foreground">Поездка оформлена · {booking.holder}</p>
        <p className="m-0 mt-0.5 text-[17px] leading-tight font-semibold tracking-tight text-foreground">
          {booking.name}, {spanText(booking.dates.from, booking.dates.to)}
        </p>
        <p className="m-0 mt-0.5 text-[13px] text-muted-foreground">
          {nightsText(booking.dates.nights)}
          {booking.extras.length > 0 && ` · ${booking.extras.map((e) => e.label).join(', ')}`}
        </p>
        <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="text-[13px] text-muted-foreground">
            Бронь <span className="font-semibold tracking-wider text-foreground tabular-nums">{booking.number}</span>
          </span>
          <span className="text-[13px] text-muted-foreground">
            Оплачено <span className="font-semibold text-foreground tabular-nums">{formatMoney(booking.total_rub, currency)}</span>
          </span>
        </div>
      </div>
    </motion.article>
  )
}
