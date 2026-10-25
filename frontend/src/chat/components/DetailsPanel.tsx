import { useEffect, type ReactNode } from 'react'
import { XMarkIcon } from '@heroicons/react/20/solid'
import type { Currency } from '@/types/api'
import { CurrencyContext } from '../widgets'

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="m-0 text-xs font-semibold tracking-wider text-faint uppercase">{title}</h3>
      {children}
    </section>
  )
}

interface DetailsPanelProps {
  title: string
  currency: Currency
  onClose: () => void
  children: ReactNode
}

/** The side panel a suggested place or route opens from its card. */
export function DetailsPanel({ title, currency, onClose, children }: DetailsPanelProps) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <CurrencyContext value={currency}>
      <section aria-label={`${title}, подробнее`} className="flex h-full min-h-0 flex-col bg-card">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border pr-3 pl-5">
          <h2 className="m-0 min-w-0 flex-1 truncate text-base font-semibold tracking-tight text-foreground">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-5 py-5">{children}</div>
      </section>
    </CurrencyContext>
  )
}
