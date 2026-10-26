import { useEffect, useState } from 'react'
import { Popover } from 'radix-ui'
import { CheckIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import { CURRENCY_OPTIONS, getCurrencyChoice, onCurrencyChange, saveCurrencyChoice, type CurrencyCode } from '@/lib/currency'

function Row({ label, note, active, onPick }: { label: string; note: string; active: boolean; onPick: () => void }) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onPick}
      className={cn(
        'flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent',
        active && 'bg-accent font-medium',
      )}
    >
      <span className="w-8 shrink-0 text-faint">{note}</span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {active && <CheckIcon className="h-4 w-4 text-highlight" aria-hidden />}
    </button>
  )
}

/** Which currency the prices are in: picked here, or «по городу вылета» (tenge from Astana, roubles from Moscow). */
export function CurrencyPicker({ className }: { className?: string }) {
  const [code, setCode] = useState<CurrencyCode | null>(getCurrencyChoice)
  const [open, setOpen] = useState(false)
  useEffect(() => onCurrencyChange(() => setCode(getCurrencyChoice())), [])
  const current = CURRENCY_OPTIONS.find((o) => o.code === code)
  const choose = (picked: CurrencyCode | null) => {
    saveCurrencyChoice(picked)
    setCode(picked)
    setOpen(false)
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger
        aria-label={`Валюта: ${current?.name ?? 'по городу вылета'}`}
        className={cn(
          'inline-flex h-8 items-center gap-1 rounded-full bg-secondary/60 px-2.5 text-sm text-muted-foreground transition-colors hover:bg-secondary',
          className,
        )}
      >
        <span className="font-semibold text-highlight">{current?.sign ?? '¤'}</span>
        {current ? current.code : 'Валюта'}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          className="z-50 w-64 rounded-2xl border border-border bg-card p-2 shadow-[0_20px_50px_-24px_rgba(15,23,42,0.45)]"
        >
          <div role="listbox" aria-label="Валюта цен">
            <Row label="По городу вылета" note="авто" active={code === null} onPick={() => choose(null)} />
            {CURRENCY_OPTIONS.map((o) => (
              <Row key={o.code} label={o.name} note={o.sign} active={o.code === code} onPick={() => choose(o.code)} />
            ))}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
