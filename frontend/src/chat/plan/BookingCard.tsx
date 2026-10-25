import { motion } from 'motion/react'
import { CheckIcon } from '@heroicons/react/20/solid'
import type { BookingEvent } from '@/types/api'
import { RUB, formatMoney } from '../widgets'
import { nightsText, spanText } from './planFormat'

/** The simulated purchase, kept in the chat: the booking number, the trip, what was paid. */
export function BookingCard({ booking }: { booking: BookingEvent }) {
  const currency = booking.currency ?? RUB
  return (
    <motion.article
      aria-label={`Бронь ${booking.number}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 24 }}
      className="mt-3 flex items-start gap-4 rounded-3xl border border-primary bg-accent p-4 sm:p-5"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary">
        <CheckIcon aria-hidden className="h-6 w-6 text-primary-foreground" />
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
