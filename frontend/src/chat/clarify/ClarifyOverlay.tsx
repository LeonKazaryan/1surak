import { useEffect, useEffectEvent, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import { ArrowLeftIcon, ArrowRightIcon, CheckIcon, XMarkIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { BriefAnswers, ClarifyEvent } from '@/types/api'
import { NIGHT_OPTIONS, describeAnswers } from '../widgets'
import { knownFacts, planCards, type CardPlan } from './plan'
import { BudgetQuestion, TravelersQuestion, VibeQuestion, WhenQuestion } from './questions'
import { useClarifyAnswers, type ClarifyAnswers } from './useClarifyAnswers'

const PLANE_PATH = 'M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z'
const AUTO_NEXT_MS = 420
const TAKEOFF_MS = 650
const PEEKING_CARDS = 2

/** Routes across the sky, in a 1440×900 scene that covers the screen. */
const ROUTES = [
  { d: 'M -120 230 C 320 70, 760 380, 1560 150', dur: 16, begin: 0 },
  { d: 'M 1560 520 C 1120 380, 560 640, -120 420', dur: 21, begin: 4 },
  { d: 'M -120 800 C 420 640, 980 900, 1560 660', dur: 18, begin: 9 },
]

function PlaneGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={className}>
      <path fill="currentColor" d={PLANE_PATH} />
    </svg>
  )
}

/** The sky behind the cards: brand glows, drifting clouds and planes flying their dashed routes. */
function Sky() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1.2, ease: 'easeOut' }}
        className="absolute -top-40 -left-32 h-[34rem] w-[34rem] rounded-full bg-primary/45 blur-3xl"
      />
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1.4, ease: 'easeOut', delay: 0.1 }}
        className="absolute -right-40 -bottom-48 h-[38rem] w-[38rem] rounded-full bg-highlight/15 blur-3xl"
      />
      <svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full motion-reduce:hidden">
        <g className="art-drift-slow" opacity="0.8">
          {[
            [180, 140, 1.1],
            [980, 110, 0.8],
            [1240, 760, 1],
            [420, 720, 0.7],
          ].map(([x, y, s], i) => (
            <g key={i} transform={`translate(${x} ${y}) scale(${s})`} fill="white">
              <ellipse cx="0" cy="0" rx="46" ry="16" />
              <ellipse cx="24" cy="-12" rx="26" ry="18" />
              <ellipse cx="-18" cy="-8" rx="20" ry="14" />
            </g>
          ))}
        </g>
        {ROUTES.map((route, i) => (
          <g key={i}>
            <path d={route.d} fill="none" stroke="var(--highlight)" strokeOpacity="0.14" strokeWidth="2" strokeDasharray="2 12" strokeLinecap="round" />
            <g opacity="0.85">
              {/* the glyph points up; turned to face +x so rotate="auto" flies it nose first */}
              <g transform="rotate(90) scale(1.5) translate(-12 -12)">
                <path d={PLANE_PATH} fill="var(--highlight)" />
              </g>
              <animateMotion dur={`${route.dur}s`} begin={`${route.begin}s`} repeatCount="indefinite" rotate="auto" path={route.d} />
            </g>
          </g>
        ))}
      </svg>
    </div>
  )
}

/** The progress trail: one stop per card, and a plane that flies to the current one. */
function Trail({ plans, current, done }: { plans: CardPlan[]; current: number; done: boolean[] }) {
  if (plans.length < 2) return null
  const at = (i: number) => `${(i / (plans.length - 1)) * 100}%`
  return (
    <div className="relative mx-auto h-12 w-full max-w-[22rem]">
      <div className="absolute inset-x-0 top-3">
        <div className="absolute inset-x-0 top-0 border-t-2 border-dashed border-highlight/20" />
        <motion.div
          className="absolute top-[-1px] left-0 h-[3px] rounded-full bg-primary"
          initial={false}
          animate={{ width: at(current) }}
          transition={{ type: 'spring', stiffness: 120, damping: 20 }}
        />
        {plans.map((plan, i) => (
          <div key={plan.slot} className="absolute -top-2.5 flex -translate-x-1/2 flex-col items-center" style={{ left: at(i) }}>
            <motion.span
              initial={false}
              animate={{ scale: i === current ? 1.15 : 1 }}
              className={cn(
                'flex h-5 w-5 items-center justify-center rounded-full border-2 transition-colors duration-300',
                done[i] ? 'border-primary bg-primary text-primary-foreground' : i === current ? 'border-highlight bg-white' : 'border-faintest bg-white',
              )}
            >
              {done[i] && <CheckIcon className="h-3 w-3" aria-hidden />}
            </motion.span>
            <span className={cn('mt-1.5 text-[11px] font-medium whitespace-nowrap', i === current ? 'text-foreground' : 'text-faint')}>
              {plan.label}
            </span>
          </div>
        ))}
        <motion.div
          className="absolute -top-9 -ml-2.5"
          initial={false}
          animate={{ left: at(current) }}
          transition={{ type: 'spring', stiffness: 90, damping: 16 }}
        >
          <PlaneGlyph className="h-5 w-5 rotate-90 text-highlight drop-shadow-[0_4px_6px_rgba(10,64,209,0.4)]" />
        </motion.div>
      </div>
    </div>
  )
}

/** Forward: the answered card takes off up and to the right, the next one rises from the deck.
 *  Back: the previous card swings in from the left, the current one sinks back into the deck. */
const card: Variants = {
  enter: (dir: number) =>
    dir >= 0 ? { opacity: 0, y: 26, scale: 0.93, x: 0, rotate: 0 } : { opacity: 0, x: '-60%', y: -10, rotate: -9, scale: 0.98 },
  center: { opacity: 1, x: 0, y: 0, scale: 1, rotate: 0, transition: { type: 'spring', stiffness: 260, damping: 25 } },
  exit: (dir: number) =>
    dir >= 0
      ? { opacity: 0, x: '70%', y: -70, rotate: 9, scale: 0.96, transition: { duration: 0.42, ease: [0.45, 0, 0.2, 1] } }
      : { opacity: 0, y: 26, scale: 0.93, transition: { duration: 0.3 } },
  takeoff: { opacity: 0, x: '35%', y: -180, rotate: -7, scale: 0.9, transition: { duration: 0.5, ease: [0.5, 0, 0.75, 0] } },
}

interface DeckCardProps {
  plan: CardPlan
  index: number
  total: number
  answered: boolean
  canSubmit: boolean
  children: ReactNode
  onBack: () => void
  onNext: () => void
}

function DeckCard({ plan, index, total, answered, canSubmit, children, onBack, onNext }: DeckCardProps) {
  const last = index === total - 1
  const ready = last ? canSubmit : answered
  return (
    <div className="rounded-[28px] border border-border bg-card p-5 shadow-[0_40px_90px_-40px_rgba(15,23,42,0.5)] sm:p-7">
      <p className="m-0 text-xs font-semibold tracking-wider text-faint uppercase">
        Вопрос {index + 1} из {total}
      </p>
      <h2 className="m-0 mt-1 text-[24px] leading-tight font-semibold tracking-tight text-foreground sm:text-[26px]">{plan.title}</h2>
      {plan.hint && <p className="m-0 mt-1 text-sm leading-snug text-muted-foreground">{plan.hint}</p>}
      <div className="mt-5">{children}</div>
      <div className="mt-6 flex items-center gap-2">
        {index > 0 && (
          <button
            type="button"
            onClick={onBack}
            className="inline-flex h-11 items-center gap-1.5 rounded-full px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <ArrowLeftIcon className="h-4 w-4" aria-hidden />
            Назад
          </button>
        )}
        <motion.button
          type="button"
          onClick={onNext}
          disabled={!ready}
          whileHover={ready ? { scale: 1.03 } : undefined}
          whileTap={ready ? { scale: 0.96 } : undefined}
          animate={ready && last ? { boxShadow: ['0 10px 24px -12px rgba(84,160,40,0.9)', '0 10px 34px -8px rgba(84,160,40,0.9)'] } : undefined}
          transition={ready && last ? { repeat: Infinity, repeatType: 'reverse', duration: 0.9 } : undefined}
          className={cn(
            'ml-auto inline-flex h-12 items-center gap-2 rounded-full px-6 text-[15px] font-semibold transition-colors duration-300',
            ready ? 'bg-primary text-primary-foreground hover:bg-primary-hover' : 'bg-secondary text-faint',
          )}
        >
          {last ? 'Подобрать направления' : 'Дальше'}
          {last ? <PlaneGlyph className="h-4 w-4 rotate-45" /> : <ArrowRightIcon className="h-4 w-4" aria-hidden />}
        </motion.button>
      </div>
    </div>
  )
}

interface ClarifyOverlayProps {
  widget: ClarifyEvent
  intro: string
  answers: ClarifyAnswers
  busy: boolean
  onClose: () => void
  onDone: (text: string, answers: BriefAnswers) => void
}

function ClarifyOverlay({ widget, intro, answers, busy, onClose, onDone }: ClarifyOverlayProps) {
  const plans = planCards(widget)
  const [[current, direction], setStep] = useState<[number, number]>([0, 1])
  const [furthest, setFurthest] = useState(0)
  const [leaving, setLeaving] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const dialog = useRef<HTMLDivElement>(null)
  const facts = knownFacts(widget.prefill)
  const done = plans.map((p) => answers.answered[p.slot])
  // a default (2 adults) counts as an answer, but the trail ticks only the stops already reached
  const ticked = done.map((d, i) => d && i <= furthest)
  const plan = plans[current]
  const last = current === plans.length - 1
  const canSubmit = done.every(Boolean) && !busy

  const close = useEffectEvent(() => onClose())
  useEffect(() => {
    dialog.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      clearTimeout(timer.current)
    }
  }, [])

  const go = (to: number) => {
    clearTimeout(timer.current)
    const target = Math.max(0, Math.min(plans.length - 1, to))
    setStep(([from]) => [target, target >= from ? 1 : -1])
    setFurthest((f) => Math.max(f, target))
  }
  // A single tap that completes a card moves on by itself; the last card waits for the button.
  const nextSoon = () => {
    if (last) return
    clearTimeout(timer.current)
    timer.current = setTimeout(() => go(current + 1), AUTO_NEXT_MS)
  }
  const finish = (skip = false) => {
    const collected = answers.collect()
    const text = describeAnswers(collected)
    setLeaving(true)
    timer.current = setTimeout(
      () => onDone(skip ? (text ? `${text}. Остальное не важно, подбирай` : 'Подбирай без уточнений') : text, collected),
      TAKEOFF_MS,
    )
  }

  const nightOptions =
    widget.prefill.nights && !NIGHT_OPTIONS.some((o) => o.join() === widget.prefill.nights!.join())
      ? [widget.prefill.nights, ...NIGHT_OPTIONS]
      : NIGHT_OPTIONS
  const body: Record<CardPlan['slot'], ReactNode> = {
    vibe: <VibeQuestion kinds={answers.kinds} onChange={answers.setKinds} />,
    when: (
      <WhenQuestion
        askMonth={plan.askMonth}
        askNights={plan.askNights}
        month={answers.month}
        nights={answers.nights}
        nightOptions={nightOptions}
        onMonth={(m) => {
          answers.setMonth(m)
          if (answers.nights) nextSoon()
        }}
        onNights={(n) => {
          answers.setNights(n)
          if (answers.month !== null) nextSoon()
        }}
      />
    ),
    travelers: (
      <TravelersQuestion
        askCounts={plan.askCounts}
        adults={answers.adults}
        ages={answers.ages}
        onAdults={answers.setAdults}
        onAges={answers.setAges}
      />
    ),
    budget: (
      <BudgetQuestion
        level={answers.level}
        total={answers.total}
        onLevel={(l) => {
          answers.setLevel(l)
          nextSoon()
        }}
        onTotal={answers.setTotal}
      />
    ),
  }

  return (
    <motion.div
      ref={dialog}
      role="dialog"
      aria-modal="true"
      aria-label="Уточняющие вопросы"
      tabIndex={-1}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.35, ease: 'easeIn' } }}
      className="fixed inset-0 z-50 overflow-y-auto overscroll-contain bg-background/80 outline-none backdrop-blur-xl"
    >
      <Sky />
      <button
        type="button"
        onClick={onClose}
        aria-label="Закрыть вопросы"
        className="fixed top-4 right-4 z-10 flex h-11 w-11 items-center justify-center rounded-full bg-white/80 text-muted-foreground shadow-sm backdrop-blur transition-colors hover:bg-white hover:text-foreground"
      >
        <XMarkIcon className="h-5 w-5" />
      </button>

      <div className="relative mx-auto flex min-h-full w-full max-w-[580px] flex-col justify-center gap-5 px-4 py-14">
        <motion.header
          initial={{ opacity: 0, y: -14 }}
          animate={leaving ? { opacity: 0, y: -20 } : { opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 220, damping: 24, delay: leaving ? 0 : 0.1 }}
          className="flex items-end gap-3"
        >
          <motion.img
            src="/mascot.png"
            alt=""
            draggable={false}
            animate={{ y: [0, -5, 0] }}
            transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
            className="h-16 w-16 shrink-0 object-contain drop-shadow-[0_10px_12px_rgba(15,23,42,0.18)]"
          />
          <div className="relative min-w-0 rounded-2xl rounded-bl-md border border-border bg-white/90 px-4 py-3 shadow-sm backdrop-blur">
            <p className="m-0 text-[15px] leading-snug text-foreground">{intro || 'Уточню пару вещей, чтобы подобрать места.'}</p>
            {facts.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-semibold tracking-wider text-faint uppercase">Уже знаю</span>
                {facts.map((fact, i) => (
                  <motion.span
                    key={fact}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.35 + i * 0.06, type: 'spring', stiffness: 400, damping: 24 }}
                    className="rounded-full bg-accent px-2 py-0.5 text-[12px] font-medium text-foreground"
                  >
                    {fact}
                  </motion.span>
                ))}
              </div>
            )}
          </div>
        </motion.header>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: leaving ? 0 : 1 }} transition={{ delay: leaving ? 0 : 0.25 }}>
          <Trail plans={plans} current={current} done={ticked} />
        </motion.div>

        <div className="relative isolate">
          {/* the rest of the deck peeking out from under the current card */}
          {Array.from({ length: Math.min(PEEKING_CARDS, plans.length - current - 1) }, (_, i) => i + 1).map((depth) => (
            <motion.div
              key={depth}
              aria-hidden
              initial={{ opacity: 0, y: 0, scale: 1 }}
              animate={leaving ? { opacity: 0 } : { opacity: 1 - depth * 0.28, y: depth * 14, scale: 1 - depth * 0.045 }}
              transition={{ type: 'spring', stiffness: 220, damping: 24, delay: leaving ? 0 : 0.15 + depth * 0.06 }}
              className="absolute inset-0 rounded-[28px] border border-border bg-card shadow-[0_20px_40px_-30px_rgba(15,23,42,0.5)]"
              style={{ zIndex: -depth }}
            />
          ))}
          <AnimatePresence mode="popLayout" custom={direction} initial>
            <motion.div
              key={plan.slot}
              custom={direction}
              variants={card}
              initial="enter"
              animate={leaving ? 'takeoff' : 'center'}
              exit="exit"
              className="relative"
            >
              <DeckCard
                plan={plan}
                index={current}
                total={plans.length}
                answered={done[current]}
                canSubmit={canSubmit}
                onBack={() => go(current - 1)}
                onNext={() => (last ? finish() : go(current + 1))}
              >
                {body[plan.slot]}
              </DeckCard>
            </motion.div>
          </AnimatePresence>
        </div>

        <motion.button
          type="button"
          initial={{ opacity: 0 }}
          animate={{ opacity: leaving ? 0 : 1 }}
          transition={{ delay: leaving ? 0 : 0.6 }}
          onClick={() => finish(true)}
          disabled={busy || leaving}
          className="mx-auto mt-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          Пропустить вопросы, подбирай как есть
        </motion.button>
      </div>

      <AnimatePresence>
        {leaving && (
          <motion.div
            key="takeoff"
            aria-hidden
            initial={{ x: '-15vw', y: '85vh', rotate: 0, scale: 0.8 }}
            animate={{ x: '110vw', y: '-20vh', scale: 1.6 }}
            transition={{ duration: 0.9, ease: [0.4, 0, 0.6, 1] }}
            className="pointer-events-none fixed top-0 left-0 z-20"
          >
            <PlaneGlyph className="h-14 w-14 rotate-[58deg] text-highlight drop-shadow-[0_18px_24px_rgba(10,64,209,0.45)]" />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

interface ClarifyFlowProps {
  widget: ClarifyEvent
  intro: string
  open: boolean
  busy: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (text: string, answers: BriefAnswers) => void
}

/** Keeps the picked answers while the cards are closed and reopened, and sends them once they fly away. */
export function ClarifyFlow({ widget, intro, open, busy, onOpenChange, onSubmit }: ClarifyFlowProps) {
  const answers = useClarifyAnswers(widget)
  const result = useRef<{ text: string; answers: BriefAnswers } | null>(null)
  return (
    <AnimatePresence
      onExitComplete={() => {
        if (!result.current) return
        const { text, answers: picked } = result.current
        result.current = null
        onSubmit(text, picked)
      }}
    >
      {open && (
        <ClarifyOverlay
          key="clarify"
          widget={widget}
          intro={intro}
          answers={answers}
          busy={busy}
          onClose={() => onOpenChange(false)}
          onDone={(text, picked) => {
            result.current = { text, answers: picked }
            onOpenChange(false)
          }}
        />
      )}
    </AnimatePresence>
  )
}
