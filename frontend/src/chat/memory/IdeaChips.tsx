import { motion } from 'motion/react'
import { ArrowUturnLeftIcon, CalendarDaysIcon, SparklesIcon } from '@heroicons/react/20/solid'
import { ScrollRow } from '@/components/ScrollRow'
import { cn } from '@/components/ui/utils'
import { EXAMPLE_TRIPS } from '@/lib/exampleTrips'
import type { Idea } from '@/types/api'

const FALLBACK: Idea[] = EXAMPLE_TRIPS.map((trip) => ({ label: trip.label, query: trip.query }))
const GHOSTS = ['w-44', 'w-40', 'w-36']

/** A booked trip coming up, a trip left half-way, an idea in the traveller's way of travelling. */
function iconOf(idea: Idea) {
  if (idea.chat_id) return idea.query ? CalendarDaysIcon : ArrowUturnLeftIcon
  return idea.why ? SparklesIcon : null
}

interface IdeaChipsProps {
  /** null while they load */
  ideas: Idea[] | null
  failed: boolean
  onPick: (idea: Idea) => void
  disabled?: boolean
  className?: string
  /** The chip's surface: the landing sets it over its picture. */
  surface?: string
}

/** The start screen's suggestions: from the traveller's earlier trips when there are some, else for anyone. */
export function IdeaChips({ ideas, failed, onPick, disabled, className, surface = 'bg-card' }: IdeaChipsProps) {
  const shown = ideas ?? (failed ? FALLBACK : null)
  return (
    <ScrollRow label="Идеи для поездки" className={className}>
      {shown === null
        ? GHOSTS.map((width) => <span key={width} aria-hidden className={cn('h-9 shrink-0 animate-pulse rounded-full', width, surface)} />)
        : shown.map((idea, i) => {
            const Icon = iconOf(idea)
            const remembered = Boolean(idea.why)
            return (
              <motion.button
                key={idea.label}
                type="button"
                onClick={() => onPick(idea)}
                disabled={disabled}
                title={idea.why ? `${idea.query ?? idea.label}\n${idea.why}` : (idea.query ?? undefined)}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 380, damping: 28, delay: i * 0.05 }}
                className={cn(
                  'flex min-h-[36px] max-w-[19rem] shrink-0 items-center gap-2 border px-4 py-1.5 text-left text-sm transition-[transform,border-color,background-color,color] hover:-translate-y-0.5 hover:border-primary hover:bg-accent hover:text-foreground disabled:opacity-50',
                  remembered ? 'rounded-2xl border-primary/50 text-foreground' : 'rounded-full border-border text-muted-foreground',
                  surface,
                )}
              >
                {Icon && <Icon aria-hidden className="h-4 w-4 shrink-0 text-[#3f7d22]" />}
                <span className="min-w-0">
                  <span className="block truncate">{idea.label}</span>
                  {idea.why && <span className="block truncate text-[11px] leading-tight text-faint">{idea.why}</span>}
                </span>
              </motion.button>
            )
          })}
    </ScrollRow>
  )
}
