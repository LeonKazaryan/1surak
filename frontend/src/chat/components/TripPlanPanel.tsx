import { XMarkIcon } from '@heroicons/react/20/solid'

const PLAN_SLOTS = ['Направление', 'Дорога туда и обратно', 'Отель', 'Трансфер']

interface TripPlanPanelProps {
  onClose: () => void
}

export function TripPlanPanel({ onClose }: TripPlanPanelProps) {
  return (
    <section aria-label="План поездки" className="flex h-full min-h-0 flex-col bg-card">
      <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border pr-3 pl-5">
        <h2 className="m-0 text-base font-semibold tracking-tight text-foreground">План поездки</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Закрыть"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-5 py-6">
        <div className="flex flex-col items-start gap-3">
          <div>
            <p className="m-0 text-[15px] font-semibold text-foreground">Здесь появится ваша поездка</p>
            <p className="m-0 mt-1 text-[13px] leading-relaxed text-muted-foreground">
              Опишите поездку в чате. Направление, дорога, отель и трансфер соберутся здесь вместе с итоговой ценой.
            </p>
          </div>
        </div>

        <ol className="m-0 flex list-none flex-col gap-2 p-0">
          {PLAN_SLOTS.map((slot) => (
            <li
              key={slot}
              className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-faintest bg-inset px-4 py-3"
            >
              <span className="text-[13px] font-medium text-foreground">{slot}</span>
              <span className="text-xs text-faint">ещё не выбрано</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
