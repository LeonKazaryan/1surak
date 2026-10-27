import { useEffect, type ComponentType, type SVGProps } from 'react'
import { AnimatePresence, animate, motion, useMotionValue, useTransform } from 'motion/react'
import {
  BookOpenIcon,
  BriefcaseIcon,
  BuildingOffice2Icon,
  ChatBubbleLeftEllipsisIcon,
  ChevronRightIcon,
  GlobeEuropeAfricaIcon,
  MagnifyingGlassIcon,
  MapIcon,
  PaperAirplaneIcon,
  PencilSquareIcon,
  SparklesIcon,
} from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { ToolFact } from '@/types/api'
import { TOOL_SOURCES } from '../agentWork'

type Icon = ComponentType<SVGProps<SVGSVGElement>>

// what the mascot holds while a tool runs: a magnifier for the search, a suitcase for the trip
const TOOL_ICONS: Record<string, Icon> = {
  update_trip_brief: PencilSquareIcon,
  ask_user: ChatBubbleLeftEllipsisIcon,
  search_destinations: MagnifyingGlassIcon,
  get_destination: GlobeEuropeAfricaIcon,
  show_destinations: SparklesIcon,
  search_routes: MapIcon,
  search_flights: PaperAirplaneIcon,
  plan_route: PaperAirplaneIcon,
  build_trip: BriefcaseIcon,
  show_trip: SparklesIcon,
  search_hotels: BuildingOffice2Icon,
  research: BookOpenIcon,
  read_page: BookOpenIcon,
}

/** A small badge on the mascot's shoulder: what it is busy with, swapping as the work moves on. */
export function ToolBadge({ tool }: { tool: string }) {
  const Icon = TOOL_ICONS[tool]
  return (
    <AnimatePresence mode="popLayout" initial={false}>
      {Icon && (
        <motion.span
          key={tool}
          initial={{ scale: 0, rotate: -40, opacity: 0 }}
          animate={{ scale: 1, rotate: 0, opacity: 1 }}
          exit={{ scale: 0, rotate: 40, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 520, damping: 22 }}
          className="absolute -right-1.5 -bottom-1 flex h-4 w-4 items-center justify-center rounded-full bg-highlight text-white shadow-[0_2px_6px_rgba(10,64,209,0.45)] ring-2 ring-card"
          aria-hidden
        >
          <Icon className="h-2.5 w-2.5" />
        </motion.span>
      )}
    </AnimatePresence>
  )
}

/** A number that runs up from zero when it appears. */
function Ticker({ value, delay }: { value: number; delay: number }) {
  const count = useMotionValue(0)
  const shown = useTransform(count, (n) => Math.round(n).toLocaleString('ru-RU'))
  useEffect(() => {
    const controls = animate(count, value, { duration: Math.min(1.2, 0.4 + value / 400), delay, ease: [0.215, 0.61, 0.355, 1] })
    return () => controls.stop()
  }, [count, value, delay])
  return <motion.b className="font-semibold text-foreground tabular-nums">{shown}</motion.b>
}

/** What the search went through, as a funnel: «138 направлений из города › 34 места проверил › 3 подходят». */
export function FactsFunnel({ facts, className }: { facts: ToolFact[]; className?: string }) {
  if (!facts.length) return null
  return (
    <ol aria-label="Что проверил" className={cn('m-0 flex list-none flex-wrap items-center gap-x-1.5 gap-y-1 p-0 text-[12px] text-muted-foreground', className)}>
      {facts.map((fact, i) => (
        <motion.li
          key={`${fact.label}-${fact.value}`}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ type: 'spring', stiffness: 420, damping: 28, delay: i * 0.18 }}
          className="flex items-center gap-1.5"
        >
          {i > 0 && <ChevronRightIcon aria-hidden className="h-3 w-3 text-faintest" />}
          <span className={cn('rounded-full px-2 py-0.5', i === facts.length - 1 ? 'bg-accent' : 'bg-secondary')}>
            <Ticker value={fact.value} delay={i * 0.18} /> {fact.label}
          </span>
        </motion.li>
      ))}
    </ol>
  )
}

/** The sources the running tool reads, coming in one by one. */
export function SourceBadges({ tool }: { tool: string }) {
  const sources = TOOL_SOURCES[tool] ?? []
  if (!sources.length) return null
  return (
    <motion.ul key={tool} aria-label="Источники" className="m-0 flex list-none flex-wrap items-center gap-1 p-0">
      {sources.map((name, i) => (
        <motion.li
          key={name}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 + i * 0.12, duration: 0.3 }}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-1.5 py-px text-[10.5px] font-medium text-muted-foreground"
        >
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary-hover" style={{ animationDelay: `${i * 0.2}s` }} />
          {name}
        </motion.li>
      ))}
    </motion.ul>
  )
}
