import { useContext } from 'react'
import { motion } from 'motion/react'
import { cn } from '@/components/ui/utils'
import type { TripPlanEvent } from '@/types/api'
import { CurrencyContext, formatMoney } from '../widgets'
import { PlanSection } from './planParts'
import { billLines } from './planFormat'

interface Swap {
  name: string
  saves: number
}

/** The alternative hotel that saves the most, to name when the trip is over budget. */
function cheapestSwap(plan: TripPlanEvent): Swap | null {
  const swaps = plan.stops.flatMap((s) =>
    s.alternatives.filter((a) => a.total_rub < s.hotel.total_rub).map((a) => ({ name: a.name, saves: s.hotel.total_rub - a.total_rub })),
  )
  return swaps.reduce<Swap | null>((best, swap) => (!best || swap.saves > best.saves ? swap : best), null)
}

function Budget({ plan, budget }: { plan: TripPlanEvent; budget: number }) {
  const currency = useContext(CurrencyContext)
  const total = plan.costs.total
  const over = total > budget
  const partial = !over && !plan.costs.flights_complete
  const swap = over ? cheapestSwap(plan) : null
  const share = Math.min(1, total / budget)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="h-2 overflow-hidden rounded-full bg-secondary" role="img" aria-label={`${Math.round((total / budget) * 100)}% бюджета`}>
        <motion.div
          className={cn('h-full rounded-full', over ? 'bg-amber-400' : partial ? 'bg-faintest' : 'bg-primary')}
          initial={{ width: 0 }}
          animate={{ width: `${share * 100}%` }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
        />
      </div>
      <p className={cn('m-0 text-[13px] leading-snug', over ? 'text-amber-700' : partial ? 'text-muted-foreground' : 'text-[#3f7d22]')}>
        {over
          ? `На ${formatMoney(total - budget, currency)} больше бюджета ${formatMoney(budget, currency)}.`
          : partial
            ? `Пока без перелётов: ${formatMoney(total, currency)} из ${formatMoney(budget, currency)}.`
            : `В бюджете: остаётся ${formatMoney(budget - total, currency)} из ${formatMoney(budget, currency)}.`}
        {swap && <span className="text-muted-foreground">{` Отель «${swap.name}» дешевле на ${formatMoney(swap.saves, currency)}.`}</span>}
      </p>
    </div>
  )
}

/** What the whole trip costs for the whole party, line by line, against the budget when there is one. */
export function PlanBill({ plan }: { plan: TripPlanEvent }) {
  const currency = useContext(CurrencyContext)
  const { costs } = plan
  return (
    <PlanSection title="Стоимость">
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {billLines(plan).map((line, i) => (
          <li key={`${i}-${line.label}`} className="flex items-baseline gap-3">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[14px] text-foreground">{line.label}</span>
              <span className="block text-[12px] text-muted-foreground">{line.note}</span>
            </span>
            <span className="shrink-0 text-[14px] font-medium text-foreground tabular-nums">{formatMoney(line.rub, currency)}</span>
          </li>
        ))}
      </ul>
      <div className="flex items-baseline gap-3 border-t border-border pt-3">
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] font-semibold text-foreground">Итого</span>
          <span className="block text-[12px] text-muted-foreground">{`${formatMoney(costs.per_person, currency)} на человека`}</span>
        </span>
        <span className="shrink-0 text-xl font-semibold tracking-tight text-foreground tabular-nums">{formatMoney(costs.total, currency)}</span>
      </div>
      {costs.budget ? <Budget plan={plan} budget={costs.budget} /> : null}
    </PlanSection>
  )
}
