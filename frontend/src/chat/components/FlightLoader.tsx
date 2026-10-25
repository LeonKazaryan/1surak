import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CheckIcon } from '@heroicons/react/16/solid'
import type { ChatTraceStep } from '../types'

/** What each tool really does, shown in turn under the step title while it runs. */
const TOOL_LINES: Record<string, string[]> = {
  update_trip_brief: ['Выделяю даты, бюджет и состав', 'Ищу скрытые пожелания'],
  ask_user: ['Оставляю только нужные вопросы'],
  search_destinations: ['Сверяю климат по месяцам', 'Считаю время в пути', 'Проверяю визы', 'Отсеиваю неподходящее'],
  get_destination: ['Изучаю детали направления'],
  show_destinations: ['Объясняю, почему эти места', 'Раскладываю карточки'],
}
const START_LINES = ['Читаю запрос', 'Думаю, с чего начать']
const LINE_MS = 2200
const SHOWN_DONE = 3

function Plane() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-4 w-4 rotate-90 text-highlight drop-shadow-[0_3px_4px_rgba(10,64,209,0.45)]">
      <path
        fill="currentColor"
        d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"
      />
    </svg>
  )
}

function Continents() {
  return (
    <svg viewBox="0 0 72 36" className="h-full w-1/2 shrink-0" aria-hidden>
      <path d="M6 10c4-4 12-4 14 1s-3 6-1 10-6 6-9 2-8-9-4-13z" fill="#adef81" />
      <path d="M28 6c5-2 9 1 8 5s4 4 2 8-8 2-9-2-5-9-1-11z" fill="#adef81" />
      <path d="M46 14c4-3 12-2 16 2s0 9-5 8-6 4-10 1 -5-8-1-11z" fill="#adef81" />
      <path d="M33 26c3-1 6 1 5 4s-6 2-6-1z" fill="#adef81" />
    </svg>
  )
}

function PlaneOrbit() {
  return (
    <div className="relative h-16 w-16 shrink-0" aria-hidden>
      <div className="absolute inset-[15px] overflow-hidden rounded-full bg-linear-to-b from-[#dff3ff] to-[#9fd4ff] shadow-[inset_-4px_-5px_8px_rgba(10,64,209,0.18)]">
        <div className="animate-globe-spin flex h-full w-[200%]">
          <Continents />
          <Continents />
        </div>
      </div>
      <svg viewBox="0 0 64 64" className="absolute inset-0">
        <circle cx="32" cy="32" r="27" fill="none" stroke="var(--highlight)" strokeOpacity="0.16" strokeWidth="1.5" strokeDasharray="0.5 4.5" strokeLinecap="round" />
      </svg>
      <div className="animate-orbit absolute inset-0">
        <div className="orbit-trail absolute inset-0 rounded-full" />
        <div className="absolute top-[5px] left-1/2 -translate-x-1/2 -translate-y-1/2">
          <Plane />
        </div>
      </div>
    </div>
  )
}

/** Cycles through what the current tool does. Keyed by the tool, so a new step starts from its first line. */
function RotatingLine({ lines }: { lines: string[] }) {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    if (lines.length < 2) return
    const timer = setInterval(() => setIndex((i) => (i + 1) % lines.length), LINE_MS)
    return () => clearInterval(timer)
  }, [lines.length])
  const line = lines[index % lines.length]
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.p
        key={line}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3 }}
        className="m-0 mt-0.5 truncate text-[13px] text-muted-foreground"
      >
        {line}…
      </motion.p>
    </AnimatePresence>
  )
}

interface FlightLoaderProps {
  steps: ChatTraceStep[]
}

/** Shown while the agent works: a plane circling the globe, the current step and what is already done. */
export function FlightLoader({ steps }: FlightLoaderProps) {
  const tools = steps.filter((s) => s.kind === 'tool')
  const running = tools.findLast((s) => s.status === 'running')
  const done = tools.filter((s) => s.status === 'done').slice(-SHOWN_DONE)
  const current = running ?? tools.at(-1)
  const title = running?.title ?? (tools.length ? 'Думаю над следующим шагом' : 'Разбираю запрос')
  const toolName = current?.name ?? ''

  return (
    <motion.div
      role="status"
      aria-live="polite"
      aria-label="Агент работает"
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -6, scale: 0.97, filter: 'blur(4px)', transition: { duration: 0.22 } }}
      transition={{ type: 'spring', stiffness: 320, damping: 28 }}
      className="relative flex items-center gap-4 overflow-hidden rounded-2xl border border-border bg-card py-3 pr-5 pl-3 shadow-[0_16px_40px_-28px_rgba(15,23,42,0.4)]"
    >
      <span aria-hidden className="absolute top-1/2 -left-8 h-32 w-32 -translate-y-1/2 rounded-full bg-primary/35 blur-2xl" />
      <div className="relative">
        <PlaneOrbit />
      </div>
      <div className="relative min-w-0 flex-1">
        <AnimatePresence mode="wait" initial={false}>
          <motion.p
            key={title}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25 }}
            className="text-shimmer m-0 truncate text-[15px] font-semibold tracking-tight"
          >
            {title}
          </motion.p>
        </AnimatePresence>
        <RotatingLine key={toolName} lines={TOOL_LINES[toolName] ?? START_LINES} />
        {done.length > 0 && (
          <ul className="m-0 mt-2 flex list-none flex-wrap gap-1.5 p-0">
            <AnimatePresence initial={false}>
              {done.map((step) => (
                <motion.li
                  key={step.id}
                  layout
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ type: 'spring', stiffness: 420, damping: 26 }}
                  className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-[11px] font-medium text-foreground"
                >
                  <CheckIcon className="h-3 w-3 text-highlight" aria-hidden />
                  {step.title}
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </motion.div>
  )
}
