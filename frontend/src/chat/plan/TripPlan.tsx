import { useState } from 'react'
import { motion } from 'motion/react'
import { ArrowPathIcon, CheckIcon, ExclamationTriangleIcon } from '@heroicons/react/20/solid'
import type { BookingEvent, PlanHotel, TripPlanEvent } from '@/types/api'
import { cn } from '@/components/ui/utils'
import { CurrencyContext, RUB, formatMoney } from '../widgets'
import { TripArt } from '../components/TripArt'
import { CheckoutSheet, type BookFn } from './CheckoutSheet'
import { PlanBill } from './PlanBill'
import { PlanDays } from './PlanDays'
import { PlanRoad } from './PlanRoad'
import { PlanStay } from './PlanStay'
import { nightsText, partyText, spanText } from './planFormat'

function Hero({ plan }: { plan: TripPlanEvent }) {
  return (
    <div className="relative h-56 sm:h-64">
      <div className="absolute inset-0 flex">
        {plan.stops.map((stop) => (
          <div key={stop.place_id} className="relative min-w-0 flex-1 overflow-hidden">
            <TripArt kind={stop.kinds[0] ?? 'sea'} seed={stop.place_id} photo={stop.photo} still className="absolute inset-0" />
          </div>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-0 bg-linear-to-t from-slate-950/80 via-slate-950/20 to-slate-950/10" />
      <span className="absolute top-3 left-3 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-foreground shadow-sm backdrop-blur">
        План поездки
      </span>
      <div className="absolute inset-x-4 bottom-4 sm:inset-x-6 sm:bottom-5">
        <h3 className="m-0 text-[28px] leading-tight font-semibold tracking-tight text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.35)]">
          {plan.name}
        </h3>
        <p className="m-0 mt-1 text-[14px] font-medium text-white/90">
          {`${spanText(plan.dates.from, plan.dates.to)} · ${nightsText(plan.dates.nights)} · ${partyText(plan.party)}`}
        </p>
      </div>
    </div>
  )
}

interface NoteProps {
  title: string
  lines: string[]
  icon: typeof ArrowPathIcon
  tone: string
  iconTone: string
}

function Note({ title, lines, icon: Icon, tone, iconTone }: NoteProps) {
  if (!lines.length) return null
  return (
    <section aria-label={title} className={cn('rounded-2xl p-4', tone)}>
      <p className="m-0 flex items-center gap-2 text-[13px] font-semibold text-foreground">
        <Icon aria-hidden className={cn('h-4 w-4', iconTone)} />
        {title}
      </p>
      <ul className="m-0 mt-1.5 flex list-none flex-col gap-1 p-0 text-[13px] leading-snug text-foreground">
        {lines.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
    </section>
  )
}

function Notes({ plan }: { plan: TripPlanEvent }) {
  if (!plan.changes.length && !plan.unmet.length) return null
  return (
    <div className="flex flex-col gap-2 px-4 pt-4 sm:px-6">
      <Note title="Что изменилось" lines={plan.changes} icon={ArrowPathIcon} tone="bg-accent" iconTone="text-[#3f7d22]" />
      <Note title="Чего не нашёл" lines={plan.unmet} icon={ExclamationTriangleIcon} tone="bg-amber-50" iconTone="text-amber-500" />
    </div>
  )
}

interface CheckoutBarProps {
  plan: TripPlanEvent
  booking?: BookingEvent
  canAct: boolean
  onCheckout: () => void
}

/** Stays at the bottom of the screen while the plan is in view: the total and the one next step. */
function CheckoutBar({ plan, booking, canAct, onCheckout }: CheckoutBarProps) {
  return (
    <div className="sticky bottom-3 z-10 mx-2 mb-2 rounded-2xl border border-border bg-card/95 px-3 py-3 shadow-[0_10px_30px_-14px_rgba(15,23,42,0.3)] backdrop-blur-md sm:mx-3 sm:mb-3 sm:px-4">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <span className="block text-[12px] text-muted-foreground">Вся поездка</span>
          <span className="block text-lg leading-tight font-semibold tracking-tight text-foreground tabular-nums">
            {formatMoney(plan.costs.total, plan.currency ?? RUB)}
          </span>
        </div>
        {booking ? (
          <span className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full bg-accent px-4 text-[13px] font-semibold text-foreground">
            <CheckIcon aria-hidden className="h-4 w-4 text-[#3f7d22]" />
            Оформлено · {booking.number}
          </span>
        ) : (
          canAct && (
            <motion.button
              type="button"
              onClick={onCheckout}
              whileTap={{ scale: 0.96 }}
              className="h-11 shrink-0 rounded-full bg-primary px-6 text-[15px] font-semibold text-primary-foreground transition-colors hover:bg-primary-hover"
            >
              Оформить поездку
            </motion.button>
          )
        )}
      </div>
      <p className="m-0 mt-1.5 hidden text-[11px] text-faint sm:block">
        {hotelPrices(plan.stops.map((s) => s.hotel))}, оплата имитируется
      </p>
    </div>
  )
}

/** Whose hotel prices these are, in a few words under the checkout button. */
function hotelPrices(hotels: PlanHotel[]): string {
  if (hotels.every((h) => h.live_price)) return hotels.some((h) => h.sandbox) ? 'Цены отелей тестовые' : 'Цены отелей на ваши даты'
  return hotels.some((h) => h.real) ? 'Цены отелей ориентировочные' : 'Отели демонстрационные'
}

interface TripPlanProps {
  plan: TripPlanEvent
  /** The latest plan, with the chat idle: its buttons work. */
  canAct: boolean
  booking?: BookingEvent
  onAsk: (text: string) => void
  onBook: BookFn
}

/** The whole trip the agent assembled, from the flight out to the bill, with one checkout for all of it. */
export function TripPlan({ plan, canAct, booking, onAsk, onBook }: TripPlanProps) {
  const [checkout, setCheckout] = useState(false)
  const currency = plan.currency ?? RUB
  const road = plan.checks.filter((c) => c.kind !== 'budget')
  const guests = plan.party.adults + plan.party.children_ages.length

  return (
    <CurrencyContext value={currency}>
      <motion.article
        aria-label={`План поездки: ${plan.name}`}
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: 'spring', stiffness: 220, damping: 26 }}
        className="mt-4 overflow-clip rounded-3xl border border-border bg-card shadow-[0_8px_24px_-18px_rgba(15,23,42,0.25)]"
      >
        <Hero plan={plan} />
        <Notes plan={plan} />
        <PlanRoad legs={plan.legs} checks={road} seats={guests} />
        <div className="mx-4 h-px bg-border sm:mx-6" />
        <PlanStay stops={plan.stops} canAct={canAct} onAsk={onAsk} />
        <div className="mx-4 h-px bg-border sm:mx-6" />
        <PlanDays days={plan.days} stops={plan.stops} />
        <div className="mx-4 h-px bg-border sm:mx-6" />
        <PlanBill plan={plan} />
        <CheckoutBar plan={plan} booking={booking} canAct={canAct} onCheckout={() => setCheckout(true)} />
      </motion.article>
      {/* stays mounted while open: paying adds the booking message, which ends canAct */}
      {((canAct && !booking) || checkout) && (
        <CheckoutSheet plan={plan} open={checkout} onOpenChange={setCheckout} onBook={onBook} />
      )}
    </CurrencyContext>
  )
}
