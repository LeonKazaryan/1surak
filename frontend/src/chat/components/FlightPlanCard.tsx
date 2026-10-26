import { useContext } from 'react'
import { motion } from 'motion/react'
import { ArrowTopRightOnSquareIcon, CheckIcon, MinusIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { FlightConnection, FlightPlan, FlightPlanEvent, FlightPlanLeg, FlightTicket } from '@/types/api'
import { CurrencyContext, RUB, formatMoney } from '../widgets'
import { ModeIcon } from './LegRow'
import { AirlineLogo } from './ticket'
import { hours, shortDate, stopsText } from './ticketFormat'

const SPRING = { type: 'spring', stiffness: 260, damping: 26 } as const

/** A ticket as one line that opens Aviasales: the buy link is the whole row. */
function TicketLine({ ticket, label }: { ticket: FlightTicket; label?: string }) {
  const currency = useContext(CurrencyContext)
  return (
    <a
      href={ticket.link}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-center gap-2 rounded-lg px-1.5 py-1 text-[12px] text-muted-foreground transition-colors hover:bg-accent/60"
    >
      <AirlineLogo ticket={ticket} className="h-4 w-4" />
      <span className="min-w-0 flex-1 truncate">
        {label && <span className="font-medium text-foreground">{label} · </span>}
        {shortDate(ticket.departure)} · {ticket.airline_name} ·{' '}
        <span className={ticket.transfers === 0 ? 'font-medium text-[#4c9a2a]' : undefined}>{stopsText(ticket)}</span>
        {ticket.hours > 0 && ` · ${hours(ticket.hours)}`}
      </span>
      <span className="shrink-0 font-semibold text-foreground tabular-nums">{formatMoney(ticket.price_rub, currency)}</span>
      <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5 shrink-0 text-faint group-hover:text-foreground" aria-hidden />
    </a>
  )
}

function Connection({ via }: { via: FlightConnection }) {
  const currency = useContext(CurrencyContext)
  return (
    <div className="mt-1 rounded-xl bg-primary/15 px-2 py-1.5">
      <p className="m-0 px-1.5 text-[12px] text-foreground">
        <span className="font-semibold">Дешевле через {via.via}</span>
        {via.saves_rub ? `: −${formatMoney(via.saves_rub, currency)}` : ''} · пересадка {hours(via.layover_hours)}, всего{' '}
        {hours(via.hours)}
        <span className="text-muted-foreground"> · два отдельных билета</span>
      </p>
      {via.tickets.map((t, i) => (
        <TicketLine key={t.link + i} ticket={t} label={i === 0 ? `до ${via.via}` : `из ${via.via}`} />
      ))}
    </div>
  )
}

function Leg({ leg, index }: { leg: FlightPlanLeg; index: number }) {
  const currency = useContext(CurrencyContext)
  const { ticket } = leg
  return (
    <motion.li
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ ...SPRING, delay: 0.1 + index * 0.06 }}
      className="list-none"
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
            leg.mode === 'flight' ? 'bg-highlight/10 text-highlight' : 'bg-primary/40 text-[#3f7d22]',
            leg.mode === 'none' && 'bg-secondary text-faint',
          )}
        >
          <ModeIcon mode={leg.mode === 'flight' ? 'flight' : 'ground'} className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-foreground">
              {leg.from} → {leg.to}
            </span>
            {ticket && (
              <span className="shrink-0 text-[14px] font-semibold text-foreground tabular-nums">{formatMoney(ticket.price_rub, currency)}</span>
            )}
          </div>
          {ticket ? (
            <TicketLine ticket={ticket} />
          ) : (
            <p className="m-0 px-1.5 py-1 text-[12px] text-muted-foreground">
              {leg.hours ? `~${hours(leg.hours)} · ` : ''}
              <span className="text-faint">{leg.estimate}</span>
            </p>
          )}
          {leg.via && <Connection via={leg.via} />}
        </div>
      </div>
    </motion.li>
  )
}

function Plan({ plan, index }: { plan: FlightPlan; index: number }) {
  const currency = useContext(CurrencyContext)
  const flown = plan.legs.filter((l) => l.ticket).length
  return (
    <motion.article
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...SPRING, delay: index * 0.08 }}
      className={cn(
        'flex flex-col gap-3 rounded-3xl border bg-card p-4 shadow-[0_8px_24px_-18px_rgba(15,23,42,0.25)] sm:col-span-2 sm:p-5',
        plan.best ? 'border-primary' : 'border-border',
      )}
    >
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="m-0 min-w-0 flex-1 text-[15px] leading-snug font-semibold text-foreground">{plan.name}</h3>
        {plan.best && (
          <span className="rounded-full bg-primary px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap text-primary-foreground">
            Лучший вариант
          </span>
        )}
      </header>

      <ol className="m-0 flex flex-col gap-2.5 p-0">
        {plan.legs.map((leg, i) => (
          <Leg key={`${leg.from}-${leg.to}-${i}`} leg={leg} index={i} />
        ))}
      </ol>

      <div className="rounded-2xl bg-inset px-4 py-3">
        <p className="m-0 text-[12px] text-muted-foreground">Билеты на весь маршрут, на человека, в одну сторону каждый</p>
        <p className="m-0 text-lg font-semibold text-foreground tabular-nums">
          {plan.total_rub ? `от ${formatMoney(plan.total_rub, currency)}` : 'цен пока нет'}
          {plan.total_rub !== null && !plan.total_complete && (
            <span className="ml-2 text-[12px] font-normal text-muted-foreground">без плеч, где билетов нет</span>
          )}
        </p>
        {plan.total_with_connections_rub !== null && plan.total_with_connections_rub < (plan.total_rub ?? Infinity) && (
          <p className="m-0 text-[13px] text-foreground">
            с пересадками через хабы: <span className="font-semibold tabular-nums">{formatMoney(plan.total_with_connections_rub, currency)}</span>
          </p>
        )}
        {flown > 1 && (
          <p className={cn('m-0 mt-0.5 flex items-center gap-1 text-[12px]', plan.dates_chained ? 'text-[#3f7d22]' : 'text-amber-600')}>
            {plan.dates_chained ? <CheckIcon className="h-3.5 w-3.5" aria-hidden /> : <MinusIcon className="h-3.5 w-3.5" aria-hidden />}
            {plan.dates_chained ? 'Даты состыкованы: каждый рейс после предыдущего' : 'Самые дешёвые даты не стыкуются, сверьте даты при покупке'}
          </p>
        )}
      </div>
    </motion.article>
  )
}

/** The user's own cities, priced leg by leg: every ticket opens Aviasales to buy it. */
export function FlightPlanCards({ widget }: { widget: FlightPlanEvent }) {
  return (
    <CurrencyContext.Provider value={widget.currency ?? RUB}>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {widget.plans.map((plan, i) => (
          <Plan key={plan.id} plan={plan} index={i} />
        ))}
      </div>
    </CurrencyContext.Provider>
  )
}
