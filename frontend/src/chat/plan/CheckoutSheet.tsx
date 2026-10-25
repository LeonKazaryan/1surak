import { useContext, useId, useState, type FormEvent } from 'react'
import { motion } from 'motion/react'
import { CheckIcon } from '@heroicons/react/20/solid'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/components/ui/utils'
import { useIsMobile } from '@/hooks/use-mobile'
import type { BookingEvent, PlanFix, TripPlanEvent } from '@/types/api'
import { CurrencyContext, formatMoney } from '../widgets'
import { billLines, nightsText, partyText, spanText } from './planFormat'

const NAME_ERROR = 'Укажите имя и фамилию, как в паспорте'
const BOOK_ERROR = 'Не получилось оформить. Попробуйте ещё раз.'
const MIN_NAME = 2

export type BookFn = (extras: PlanFix['id'][], holder: string) => Promise<BookingEvent>

/** The fixes the checks offer (early check-in, late check-out), once per hotel. */
function offeredExtras(plan: TripPlanEvent): PlanFix[] {
  const fixes = plan.checks.flatMap((c) => (c.fix ? [c.fix] : []))
  return fixes.filter((fix, i) => fixes.findIndex((f) => f.id === fix.id) === i)
}

function Done({ booking, onClose }: { booking: BookingEvent; onClose: () => void }) {
  const currency = useContext(CurrencyContext)
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-10 text-center">
      <motion.span
        initial={{ scale: 0.4, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 320, damping: 18 }}
        className="flex h-16 w-16 items-center justify-center rounded-full bg-primary"
      >
        <CheckIcon aria-hidden className="h-8 w-8 text-primary-foreground" />
      </motion.span>
      <div>
        <p className="m-0 text-xl font-semibold tracking-tight text-foreground">Поездка оформлена</p>
        <p className="m-0 mt-1 text-[14px] text-muted-foreground">
          {booking.name}, {spanText(booking.dates.from, booking.dates.to)}
        </p>
      </div>
      <div className="rounded-2xl bg-inset px-5 py-3">
        <span className="block text-[12px] text-muted-foreground">Номер брони</span>
        <span className="block text-2xl font-semibold tracking-wider text-foreground tabular-nums">{booking.number}</span>
      </div>
      <p className="m-0 text-[13px] text-muted-foreground">
        Оплачено {formatMoney(booking.total_rub, currency)}. Это демонстрация: деньги не списаны.
      </p>
      <button
        type="button"
        onClick={onClose}
        className="mt-2 h-11 rounded-full bg-foreground px-8 text-sm font-semibold text-white transition-opacity hover:opacity-90"
      >
        Готово
      </button>
    </div>
  )
}

interface CheckoutSheetProps {
  plan: TripPlanEvent
  open: boolean
  onOpenChange: (open: boolean) => void
  onBook: BookFn
}

/** One cart for the whole trip: what is in it, the extras the checks suggest, who travels, and a fake payment. */
export function CheckoutSheet({ plan, open, onOpenChange, onBook }: CheckoutSheetProps) {
  const currency = useContext(CurrencyContext)
  const isMobile = useIsMobile()
  const nameId = useId()
  const extras = offeredExtras(plan)
  const [chosen, setChosen] = useState<PlanFix['id'][]>([])
  const [holder, setHolder] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [paying, setPaying] = useState(false)
  const [booking, setBooking] = useState<BookingEvent | null>(null)
  const total = plan.costs.total + extras.filter((e) => chosen.includes(e.id)).reduce((sum, e) => sum + e.price_rub, 0)

  const toggle = (id: PlanFix['id']) => setChosen((now) => (now.includes(id) ? now.filter((t) => t !== id) : [...now, id]))

  const pay = async (e: FormEvent) => {
    e.preventDefault()
    const name = holder.trim()
    if (name.length < MIN_NAME) {
      setError(NAME_ERROR)
      return
    }
    setError(null)
    setPaying(true)
    try {
      setBooking(await onBook(chosen, name))
    } catch {
      setError(BOOK_ERROR)
    } finally {
      setPaying(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isMobile ? 'bottom' : 'right'}
        className={cn('gap-0 bg-card p-0', isMobile ? 'max-h-[92dvh] rounded-t-3xl' : 'w-full sm:max-w-[440px]')}
      >
        <div className="shrink-0 border-b border-border px-5 pt-5 pb-4">
          <SheetTitle className="text-lg tracking-tight">Оформление поездки</SheetTitle>
          <SheetDescription className="mt-0.5 text-[13px]">
            {plan.name} · {spanText(plan.dates.from, plan.dates.to)} · {nightsText(plan.dates.nights)} · {partyText(plan.party)}
          </SheetDescription>
        </div>

        {booking ? (
          <Done booking={booking} onClose={() => onOpenChange(false)} />
        ) : (
          <form onSubmit={pay} noValidate className="flex min-h-0 flex-1 flex-col">
            <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5">
              <section aria-label="В заказе" className="flex flex-col gap-2.5">
                <h3 className="m-0 text-xs font-semibold tracking-wider text-faint uppercase">В заказе</h3>
                <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                  {billLines(plan).map((line, i) => (
                    <li key={`${i}-${line.label}`} className="flex items-baseline gap-3">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[14px] text-foreground">{line.label}</span>
                        <span className="block text-[12px] text-muted-foreground">{line.note}</span>
                      </span>
                      <span className="shrink-0 text-[14px] font-medium tabular-nums">{formatMoney(line.rub, currency)}</span>
                    </li>
                  ))}
                </ul>
              </section>

              {extras.length > 0 && (
                <section aria-label="Добавить" className="flex flex-col gap-2">
                  <h3 className="m-0 text-xs font-semibold tracking-wider text-faint uppercase">Добавить</h3>
                  {extras.map((extra) => (
                    <label
                      key={extra.id}
                      className="flex cursor-pointer items-center gap-3 rounded-2xl border border-border px-4 py-3 transition-colors has-checked:border-primary has-checked:bg-accent"
                    >
                      <input
                        type="checkbox"
                        checked={chosen.includes(extra.id)}
                        onChange={() => toggle(extra.id)}
                        className="h-5 w-5 shrink-0 accent-(--highlight)"
                      />
                      <span className="min-w-0 flex-1 text-[14px] font-medium text-foreground">{extra.label}</span>
                      <span className="shrink-0 text-[14px] text-muted-foreground tabular-nums">+{formatMoney(extra.price_rub, currency)}</span>
                    </label>
                  ))}
                </section>
              )}

              <div className="flex flex-col gap-1.5">
                <label htmlFor={nameId} className="text-[13px] font-medium text-foreground">
                  Имя и фамилия
                </label>
                <input
                  id={nameId}
                  value={holder}
                  onChange={(e) => setHolder(e.target.value)}
                  autoComplete="name"
                  maxLength={80}
                  placeholder="Как в паспорте"
                  aria-invalid={error === NAME_ERROR || undefined}
                  className="h-12 rounded-xl border border-border bg-input-background px-4 text-[16px] text-foreground outline-none placeholder:text-faint focus:border-highlight"
                />
                {error && (
                  <p role="alert" className="m-0 text-[13px] text-danger">
                    {error}
                  </p>
                )}
              </div>
            </div>

            <div className="shrink-0 border-t border-border px-5 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
              <button
                type="submit"
                disabled={paying}
                className="h-12 w-full rounded-full bg-primary text-[15px] font-semibold text-primary-foreground transition-colors hover:bg-primary-hover disabled:opacity-60"
              >
                {paying ? 'Оформляю' : `Оплатить ${formatMoney(total, currency)}`}
              </button>
              <p className="m-0 mt-2 text-center text-[11px] text-faint">Оплата имитируется: деньги не списываются, отели демонстрационные</p>
            </div>
          </form>
        )}
      </SheetContent>
    </Sheet>
  )
}
