import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { cn } from '@/components/ui/utils'
import { BrandBackdrop } from '../map/BrandBackdrop'

/** What happens while the card is put together, in the order it happens, round and round until it is there. */
const LINES = {
  plan: ['Подбираю фотографии', 'Раскладываю дни по районам', 'Проверяю стыковки рейсов и заселения', 'Считаю итог поездки', 'Оформляю карточку'],
  cards: ['Подбираю фотографии мест', 'Сверяю погоду и билеты', 'Отмечаю визы', 'Раскладываю карточки'],
}
const LINE_MS = 2400
const SPRING = { type: 'spring', stiffness: 260, damping: 28 } as const

function useLine(lines: string[]): string {
  const [at, setAt] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setAt((i) => (i + 1) % lines.length), LINE_MS)
    return () => clearInterval(timer)
  }, [lines.length])
  return lines[at % lines.length]
}

function Status({ line }: { line: string }) {
  return (
    <div className="flex items-center gap-2.5 px-5 pt-4" role="status" aria-live="polite">
      <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden>
        <span className="absolute inset-0 rounded-full bg-primary motion-safe:animate-ping" />
        <span className="relative h-2.5 w-2.5 rounded-full bg-[#4c9a2a]" />
      </span>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={line}
          initial={{ opacity: 0, y: 6, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -6, filter: 'blur(4px)' }}
          transition={{ duration: 0.3 }}
          className="text-shimmer text-[14px] font-medium"
        >
          {line}…
        </motion.span>
      </AnimatePresence>
    </div>
  )
}

function Bar({ className }: { className: string }) {
  return <span aria-hidden className={cn('block rounded-full bg-secondary motion-safe:animate-pulse', className)} />
}

interface PlanPendingProps {
  kind: 'plan' | 'cards'
  /** The trip's place, from its cover: «Нячанг». */
  place?: string | null
  /** The cover's photo, faded in behind the title when there is one. */
  photo?: string | null
}

/** The card being put together: the place and its photo come first, then what the agent is doing, so the
 * seconds before the plan or the cards are not an empty screen. */
export function PlanPending({ kind, place, photo }: PlanPendingProps) {
  const line = useLine(LINES[kind])
  const [loaded, setLoaded] = useState(false)
  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8 }}
      transition={SPRING}
      className="overflow-hidden rounded-[28px] border border-border bg-card shadow-[0_24px_60px_-42px_rgba(15,23,42,0.55)]"
      aria-label={kind === 'plan' ? 'Собираю план поездки' : 'Собираю подборку'}
    >
      {kind === 'plan' ? (
        <div className="relative isolate flex h-40 items-end overflow-hidden sm:h-48">
          <BrandBackdrop />
          {photo && (
            <motion.img
              src={photo}
              alt=""
              draggable={false}
              onLoad={() => setLoaded(true)}
              initial={{ opacity: 0, scale: 1.06 }}
              animate={{ opacity: loaded ? 1 : 0, scale: loaded ? 1 : 1.06 }}
              transition={{ duration: 1.1, ease: 'easeOut' }}
              className="absolute inset-0 h-full w-full object-cover"
            />
          )}
          {photo && loaded && <span aria-hidden className="absolute inset-0 bg-linear-to-t from-slate-950/70 via-slate-950/20 to-transparent" />}
          <span className="absolute top-4 left-4 rounded-full bg-white/90 px-3 py-1 text-[12px] font-semibold text-foreground shadow-sm">
            План поездки
          </span>
          {/* a light sweep across the picture while it is being put together */}
          <span aria-hidden className="cover-sweep absolute inset-0" />
          <motion.h3
            initial={{ opacity: 0, y: 10, filter: 'blur(6px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ ...SPRING, delay: 0.15 }}
            className={cn(
              'relative m-0 px-5 pb-4 text-[28px] leading-tight font-semibold tracking-tight',
              photo && loaded ? 'text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.35)]' : 'text-foreground',
            )}
          >
            {place || 'Ваша поездка'}
          </motion.h3>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 p-4 pb-0">
          {[0, 1].map((i) => (
            <span key={i} aria-hidden className="relative block h-32 overflow-hidden rounded-2xl bg-secondary">
              <span className="cover-sweep absolute inset-0" style={{ animationDelay: `${i * 0.4}s` }} />
            </span>
          ))}
        </div>
      )}
      <Status line={line} />
      <div className="flex flex-col gap-2.5 px-5 pt-3 pb-5">
        <Bar className="h-3 w-3/4" />
        <Bar className="h-3 w-1/2" />
        {kind === 'plan' && <Bar className="h-3 w-2/3" />}
      </div>
    </motion.div>
  )
}
