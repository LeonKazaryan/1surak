import { useState } from 'react'
import { Popover } from 'radix-ui'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDownIcon, XMarkIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { MemoryFact } from '@/types/api'

interface MemoryPanelProps {
  facts: MemoryFact[]
  onForget: (key: string) => void
  className?: string
}

/** «Что я о вас помню»: a pill next to the departure city and the currency; it opens every fact the agent may
 * offer, with the trip it comes from and a way to forget it. */
export function MemoryPanel({ facts, onForget, className }: MemoryPanelProps) {
  const [open, setOpen] = useState(false)
  if (!facts.length) return null
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger
        aria-label={`Что я о вас помню: ${facts.length}`}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 rounded-full bg-secondary/60 pr-2 pl-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary',
          className,
        )}
      >
        <img src="/mascot.png" alt="" draggable={false} className="h-5 w-5 object-contain" />
        Помню о вас
        <span className="text-faint tabular-nums">· {facts.length}</span>
        <ChevronDownIcon aria-hidden className={cn('h-4 w-4 text-faint transition-transform duration-300', open && 'rotate-180')} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="center"
          sideOffset={8}
          collisionPadding={12}
          aria-label="Что я о вас помню"
          className="z-50 w-[min(26rem,92vw)] rounded-2xl border border-border bg-card p-1.5 shadow-[0_20px_50px_-24px_rgba(15,23,42,0.45)]"
        >
          <motion.div initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: 'spring', stiffness: 420, damping: 30 }}>
            <p className="m-0 px-2.5 pt-1.5 pb-1 text-[12px] font-semibold tracking-wider text-faint uppercase">Что я о вас помню</p>
            <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
              <AnimatePresence initial={false}>
                {facts.map((fact) => (
                  <motion.li
                    key={fact.key}
                    layout
                    exit={{ opacity: 0, x: -12, transition: { duration: 0.18 } }}
                    className="flex items-center gap-3 rounded-xl px-2.5 py-1.5 transition-colors hover:bg-secondary/50"
                  >
                    <span className="w-[4.5rem] shrink-0 text-[12px] text-faint">{fact.label}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] leading-snug text-foreground">{fact.text}</span>
                      <span className="block truncate text-[11px] text-faint">{fact.source}</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => onForget(fact.key)}
                      aria-label={`Забыть: ${fact.text}`}
                      title="Забыть"
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-faint transition-colors hover:bg-secondary hover:text-foreground"
                    >
                      <XMarkIcon className="h-4 w-4" />
                    </button>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
            <p className="m-0 px-2.5 pt-1.5 pb-1 text-[11px] leading-snug text-faint">
              Это из ваших поездок в этом браузере. Я предлагаю, но не решаю за вас. Удалите поездку из списка, и я её забуду.
            </p>
          </motion.div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
