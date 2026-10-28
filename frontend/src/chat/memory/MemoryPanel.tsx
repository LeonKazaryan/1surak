import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDownIcon, XMarkIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { MemoryFact } from '@/types/api'

interface MemoryPanelProps {
  facts: MemoryFact[]
  onForget: (key: string) => void
}

/** «Что я о вас помню»: every fact the agent may offer, with the trip it comes from and a way to forget it. */
export function MemoryPanel({ facts, onForget }: MemoryPanelProps) {
  const [open, setOpen] = useState(false)
  if (!facts.length) return null
  return (
    <section aria-label="Что я о вас помню" className="flex w-full flex-col items-center">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] text-muted-foreground transition-colors hover:bg-card/70 hover:text-foreground"
      >
        <img src="/mascot.png" alt="" draggable={false} className="h-5 w-5 object-contain" />
        Что я о вас помню
        <span className="text-faint tabular-nums">· {facts.length}</span>
        <ChevronDownIcon aria-hidden className={cn('h-4 w-4 transition-transform duration-300', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className="w-full max-w-md overflow-hidden"
          >
            <ul className="m-0 mt-2 flex list-none flex-col gap-0.5 rounded-2xl border border-border bg-card p-1.5 shadow-[0_18px_40px_-30px_rgba(15,23,42,0.5)]">
              <AnimatePresence initial={false}>
                {facts.map((fact) => (
                  <motion.li
                    key={fact.key}
                    layout
                    exit={{ opacity: 0, x: -12, transition: { duration: 0.18 } }}
                    className="flex items-center gap-3 rounded-xl px-2.5 py-1.5"
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
            <p className="m-0 mt-1.5 px-4 text-center text-[11px] leading-snug text-faint">
              Это из ваших поездок в этом браузере. Я предлагаю, но не решаю за вас. Удалите поездку из списка, и я её забуду.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
