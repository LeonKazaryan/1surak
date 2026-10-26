import { useEffect, useId, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CheckIcon } from '@heroicons/react/16/solid'
import { LogoMark } from '@/components/LogoMark'
import type { ChatTraceStep } from '../types'
import { LAND_PATH } from './landPath'

/** What each tool really does, shown in turn under the step title while it runs. */
const TOOL_LINES: Record<string, string[]> = {
  update_trip_brief: ['Выделяю даты, бюджет и состав', 'Ищу скрытые пожелания'],
  ask_user: ['Оставляю только нужные вопросы'],
  search_destinations: ['Сверяю климат по месяцам', 'Считаю время в пути', 'Проверяю визы', 'Отсеиваю неподходящее'],
  get_destination: ['Изучаю детали направления'],
  show_destinations: ['Объясняю, почему эти места', 'Раскладываю карточки'],
  search_routes: [
    'Связываю города в маршрут',
    'Считаю совпадение с интересами',
    'Делю ночи по городам',
    'Ищу билеты на каждое плечо',
    'Сверяю поезда и автобусы',
    'Ищу путь дешевле пересадок',
    'Стыкую даты и время',
  ],
  search_flights: ['Ищу билеты на Aviasales', 'Сравниваю прямые и с пересадкой'],
  plan_route: ['Прокладываю перелёты', 'Ищу пересадки через хабы', 'Сравниваю цены по дням'],
  build_trip: ['Подбираю отели', 'Стыкую рейсы, поезда и заселение', 'Считаю бюджет'],
  show_trip: ['Собираю план поездки'],
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

const LAND_BANDS: [number, string][] = [
  [0.07, '#eef5fb'],
  [0.17, '#4f9a4a'],
  [0.26, '#6fb65a'],
  [0.36, '#d9c287'],
  [0.43, '#a9b866'],
  [0.5, '#3d9446'],
  [0.6, '#b3b36a'],
  [0.65, '#cfb27a'],
  [0.73, '#74b85c'],
]

function Land() {
  const id = useId().replace(/:/g, '')
  return (
    <svg viewBox="0 0 144 72" className="h-full w-1/2 shrink-0" aria-hidden>
      <defs>
        <linearGradient id={id} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="72">
          {LAND_BANDS.map(([offset, color]) => (
            <stop key={offset} offset={offset} stopColor={color} />
          ))}
        </linearGradient>
      </defs>
      <path d={LAND_PATH} fill={`url(#${id})`} />
    </svg>
  )
}

function Clouds() {
  return (
    <svg viewBox="0 0 144 72" className="h-full w-1/2 shrink-0" aria-hidden>
      <g fill="#fff">
        <ellipse cx="18" cy="22" rx="14" ry="2.5" />
        <ellipse cx="58" cy="44" rx="11" ry="2" />
        <ellipse cx="92" cy="16" rx="16" ry="2.5" />
        <ellipse cx="124" cy="36" rx="12" ry="2" />
        <ellipse cx="40" cy="58" rx="13" ry="2" />
      </g>
    </svg>
  )
}

function Earth() {
  return (
    <div className="absolute inset-[13px] overflow-hidden rounded-full bg-[radial-gradient(circle_at_35%_30%,#5aa6ff,#1a5fe0_45%,#0a36a0)] shadow-[0_0_0_1px_rgba(120,180,255,0.35),0_0_8px_1px_rgba(70,140,255,0.45)]">
      <div className="animate-globe-spin flex h-full w-[400%]">
        <Land />
        <Land />
      </div>
      <div className="animate-globe-spin absolute inset-0 flex w-[400%] opacity-45 blur-[0.4px] [animation-duration:26s]">
        <Clouds />
        <Clouds />
      </div>
      <span className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_30%_25%,rgba(255,255,255,0.45),transparent_40%),radial-gradient(circle_at_40%_35%,transparent_50%,rgba(3,16,60,0.6))] shadow-[inset_0_0_3px_rgba(180,220,255,0.6)]" />
    </div>
  )
}

function PlaneOrbit() {
  return (
    <div className="relative h-16 w-16 shrink-0" aria-hidden>
      <Earth />
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
        <div className="flex min-w-0 items-center gap-1.5">
          <LogoMark className="animate-logo-pulse h-6 w-6 shrink-0" />
          <AnimatePresence mode="wait" initial={false}>
            <motion.p
              key={title}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
              className="text-shimmer m-0 min-w-0 truncate text-[15px] font-semibold tracking-tight"
            >
              {title}
            </motion.p>
          </AnimatePresence>
        </div>
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
