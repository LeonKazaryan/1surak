import { useEffect, useEffectEvent, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useSpring, type Variants } from 'motion/react'
import { ArrowLeftIcon, MapPinIcon, XMarkIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import { buildRoute } from '@/landing/route'
import { getDepartureCity } from '@/lib/departureCity'
import type { BriefAnswers, ClarifyEvent } from '@/types/api'
import { describeAnswers, plural } from '../widgets'
import { buildSteps, knownFacts, partyOptions, planCards, progressAt, type Step } from './plan'
import { AgeStep, BudgetStep, CountStep, MonthStep, NightsStep, PartyStep, VibeStep } from './questions'
import { useClarifyAnswers, type ClarifyAnswers } from './useClarifyAnswers'

const PLANE_PATH = 'M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z'
const PICK_SHOW_MS = 260 // long enough to see the pick light up before the card flies off
const ARRIVAL_MS = 1100 // the plane reaches the flag, then the cards close
const PEEKING_CARDS = 2
// Static glows instead of blurred blobs: nothing behind the cards has to repaint while they move.
const BACKDROP =
  'radial-gradient(42rem 30rem at 0% 0%, rgba(173,239,129,0.42), transparent 62%), radial-gradient(46rem 34rem at 100% 100%, rgba(10,64,209,0.11), transparent 60%)'

/** The flight from the departure city to the picks, in a 520×84 box; measured by arc length. */
const ROUTE = buildRoute([
  { x: 26, y: 58 },
  { x: 170, y: 22 },
  { x: 330, y: 60 },
  { x: 492, y: 26 },
])
const START = ROUTE.at(0)
const END = ROUTE.at(1)

interface FlightRouteProps {
  progress: number
  stops: number
  remaining: number
  arriving: boolean
}

/** One plane flies the route as the questions get answered; the trail behind it fills in lime. */
function FlightRoute({ progress, stops, remaining, arriving }: FlightRouteProps) {
  const flown = useSpring(progress, { stiffness: 48, damping: 14, mass: 1 })
  const plane = useRef<SVGGElement>(null)
  const place = (p: number) => {
    const at = ROUTE.at(p)
    plane.current?.setAttribute('transform', `translate(${at.x} ${at.y}) rotate(${at.angle + 90})`)
  }
  useEffect(() => flown.set(progress), [flown, progress])
  useLayoutEffect(() => place(flown.get()))
  useMotionValueEvent(flown, 'change', place)

  const ticks = Array.from({ length: Math.max(0, stops - 1) }, (_, i) => (i + 1) / stops)
  const caption = arriving
    ? 'Летим за подборкой'
    : remaining === 1
      ? 'Последний вопрос'
      : `Ещё ${remaining} ${plural(remaining, ['вопрос', 'вопроса', 'вопросов'])}`

  return (
    <div className="rounded-3xl border border-white/70 bg-white/60 px-4 pt-2 pb-3 shadow-[0_10px_30px_-24px_rgba(15,23,42,0.5)]">
      <svg viewBox="0 0 520 84" className="block w-full overflow-visible" aria-hidden>
        <path d={ROUTE.d} fill="none" stroke="var(--highlight)" strokeOpacity="0.2" strokeWidth="3" strokeDasharray="1 10" strokeLinecap="round" />
        <motion.path d={ROUTE.d} fill="none" stroke="var(--primary)" strokeWidth="5" strokeLinecap="round" style={{ pathLength: flown }} />
        {ticks.map((t) => {
          const at = ROUTE.at(t)
          const passed = progress >= t - 0.001
          return (
            <circle
              key={t}
              cx={at.x}
              cy={at.y}
              r="5"
              fill={passed ? 'var(--primary)' : 'white'}
              stroke={passed ? 'var(--primary)' : 'var(--faintest)'}
              strokeWidth="2"
              className="transition-[fill,stroke] duration-500"
            />
          )
        })}
        <circle cx={START.x} cy={START.y} r="6" fill="var(--highlight)" />
        <motion.g
          initial={false}
          animate={arriving ? { scale: [1, 1.3, 1] } : { scale: 1 }}
          transition={{ duration: 0.6, delay: 0.7 }}
        >
          <circle cx={END.x} cy={END.y} r="15" fill="white" stroke="var(--highlight)" strokeWidth="2.5" />
          <g transform={`translate(${END.x - 9} ${END.y - 9}) scale(0.9)`} style={{ color: 'var(--highlight)' }}>
            <MapPinIcon width={20} height={20} />
          </g>
        </motion.g>
        <g ref={plane}>
          <g transform="scale(1.45) translate(-12 -12)">
            <path d={PLANE_PATH} fill="var(--highlight)" stroke="white" strokeWidth="1.6" strokeLinejoin="round" paintOrder="stroke" />
          </g>
        </g>
      </svg>
      <div className="-mt-1 flex items-center justify-between text-[12px] font-medium">
        <span className="text-muted-foreground">{getDepartureCity().name}</span>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={caption}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className="text-foreground"
          >
            {caption}
          </motion.span>
        </AnimatePresence>
        <span className="text-muted-foreground">Подборка</span>
      </div>
    </div>
  )
}

/** Forward: the answered card takes off up and to the right, the next one rises from the deck.
 *  Back: the previous card swings in from the left, the current one sinks back into the deck. */
const card: Variants = {
  enter: (dir: number) => (dir >= 0 ? { opacity: 0, y: 24, scale: 0.94, x: 0, rotate: 0 } : { opacity: 0, x: '-55%', rotate: -8 }),
  center: { opacity: 1, x: 0, y: 0, scale: 1, rotate: 0, transition: { type: 'spring', stiffness: 300, damping: 28 } },
  exit: (dir: number) =>
    dir >= 0
      ? { opacity: 0, x: '65%', y: -60, rotate: 8, transition: { duration: 0.34, ease: [0.45, 0, 0.2, 1] } }
      : { opacity: 0, y: 24, scale: 0.94, transition: { duration: 0.24 } },
  takeoff: { opacity: 0, y: -140, x: '25%', rotate: -6, scale: 0.92, transition: { duration: 0.45, ease: [0.5, 0, 0.75, 0] } },
}

type StepPosition = [index: number, direction: number]

interface ClarifyOverlayProps {
  widget: ClarifyEvent
  intro: string
  answers: ClarifyAnswers
  position: StepPosition
  onPosition: (update: (prev: StepPosition) => StepPosition) => void
  busy: boolean
  onClose: () => void
  onDone: (text: string, answers: BriefAnswers) => void
}

function ClarifyOverlay({ widget, intro, answers, position, onPosition, busy, onClose, onDone }: ClarifyOverlayProps) {
  const plans = planCards(widget)
  const slots = plans.map((p) => p.slot)
  const steps = buildSteps(widget, { party: answers.party, ages: answers.ages })
  const [index, direction] = position
  const [picked, setPicked] = useState<number | null>(null) // the step just answered, about to move on
  const [arriving, setArriving] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const dialog = useRef<HTMLDivElement>(null)
  const current = Math.min(index, steps.length - 1)
  const step = steps[current]
  const facts = knownFacts(widget.prefill)

  const finish = (skip = false) => {
    if (arriving) return
    const collected = answers.collect()
    const text = describeAnswers(collected)
    setArriving(true)
    timer.current = setTimeout(
      () => onDone(skip ? (text ? `${text}. Остальное не важно, подбирай` : 'Подбирай без уточнений') : text, collected),
      ARRIVAL_MS,
    )
  }
  const go = (to: number) => onPosition(([from]) => [Math.max(0, to), to >= from ? 1 : -1])

  // Runs after the pick has re-rendered, so a pick that adds steps («С детьми») moves into them.
  const advance = useEffectEvent((from: number) => {
    setPicked(null)
    if (from >= steps.length - 1) finish()
    else go(from + 1)
  })
  useEffect(() => {
    if (picked === null) return
    const t = setTimeout(() => advance(picked), PICK_SHOW_MS)
    return () => clearTimeout(t)
  }, [picked])

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

  const pick = (apply: () => void) => {
    if (arriving || busy || picked !== null) return
    apply()
    setPicked(current)
  }
  const child = step.child ?? 0
  const body: Record<Step['kind'], () => ReactNode> = {
    vibe: () => <VibeStep selected={answers.kinds[0] ?? null} onPick={(k) => pick(() => answers.setKinds([k]))} />,
    month: () => <MonthStep selected={answers.month} onPick={(m) => pick(() => answers.setMonth(m))} />,
    nights: () => <NightsStep selected={answers.nights} extra={widget.prefill.nights} onPick={(n) => pick(() => answers.setNights(n))} />,
    party: () => <PartyStep choices={partyOptions(widget.prefill)} selected={answers.party} onPick={(p) => pick(() => answers.choose(p))} />,
    kids: () => (
      <CountStep
        values={[1, 2, 3, 4]}
        unit={['ребёнок', 'ребёнка', 'детей']}
        selected={answers.ages.length || null}
        onPick={(n) => pick(() => answers.setKids(n))}
      />
    ),
    adults: () => (
      <CountStep
        values={[3, 4, 5, 6, 7, 8]}
        unit={['взрослый', 'взрослых', 'взрослых']}
        selected={answers.party === 'group' ? answers.adults : null}
        onPick={(n) => pick(() => answers.setAdults(n))}
      />
    ),
    age: () => <AgeStep selected={answers.ages[child] ?? null} onPick={(a) => pick(() => answers.setAge(child, a))} />,
    budget: () => (
      <BudgetStep level={answers.level} onLevel={(l) => pick(() => answers.setLevel(l))} onTotal={(t) => pick(() => answers.setTotal(t))} />
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
      exit={{ opacity: 0, transition: { duration: 0.3, ease: 'easeIn' } }}
      className="fixed inset-0 z-50 overflow-y-auto overscroll-contain bg-background outline-none"
      style={{ backgroundImage: BACKDROP }}
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Закрыть вопросы"
        className="fixed top-4 right-4 z-10 flex h-11 w-11 items-center justify-center rounded-full bg-white text-muted-foreground shadow-sm transition-colors hover:text-foreground"
      >
        <XMarkIcon className="h-5 w-5" />
      </button>

      {/* pinned to the top, not centred: cards differ in height, and the route must not jump between them */}
      <div className="relative mx-auto flex w-full max-w-[580px] flex-col gap-4 px-4 pt-16 pb-10 sm:pt-[9vh]">
        <motion.header
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 260, damping: 26, delay: 0.05 }}
          className="flex items-end gap-3"
        >
          <img src="/mascot.png" alt="" draggable={false} className="h-14 w-14 shrink-0 object-contain" />
          <div className="min-w-0 rounded-2xl rounded-bl-md border border-border bg-white px-4 py-3 shadow-sm">
            <p className="m-0 text-[15px] leading-snug text-foreground">{intro || 'Уточню пару вещей, чтобы подобрать места.'}</p>
            {facts.length > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-semibold tracking-wider text-faint uppercase">Уже знаю</span>
                {facts.map((fact) => (
                  <span key={fact} className="rounded-full bg-accent px-2 py-0.5 text-[12px] font-medium text-foreground">
                    {fact}
                  </span>
                ))}
              </div>
            )}
          </div>
        </motion.header>

        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
          <FlightRoute
            progress={arriving ? 1 : progressAt(steps, current, slots)}
            stops={slots.length}
            remaining={slots.length - slots.indexOf(step.slot)}
            arriving={arriving}
          />
        </motion.div>

        <div className="relative isolate">
          {/* the rest of the deck peeking out from under the current card */}
          {Array.from({ length: Math.min(PEEKING_CARDS, steps.length - current - 1) }, (_, i) => i + 1).map((depth) => (
            <motion.div
              key={depth}
              aria-hidden
              initial={false}
              animate={arriving ? { opacity: 0 } : { opacity: 1 - depth * 0.3, y: depth * 12, scale: 1 - depth * 0.04 }}
              transition={{ type: 'spring', stiffness: 260, damping: 26 }}
              className="absolute inset-0 rounded-[28px] border border-border bg-card"
              style={{ zIndex: -depth }}
            />
          ))}
          <AnimatePresence mode="popLayout" custom={direction} initial>
            <motion.section
              key={step.key}
              custom={direction}
              variants={card}
              initial="enter"
              animate={arriving ? 'takeoff' : 'center'}
              exit="exit"
              className="relative rounded-[28px] border border-border bg-card p-5 shadow-[0_30px_60px_-36px_rgba(15,23,42,0.5)] sm:p-7"
            >
              <div className="flex min-h-9 items-center gap-2">
                {current > 0 && (
                  <button
                    type="button"
                    onClick={() => go(current - 1)}
                    aria-label="Назад"
                    className="-ml-2 flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                  >
                    <ArrowLeftIcon className="h-4 w-4" />
                  </button>
                )}
                <span className="text-xs font-semibold tracking-wider text-faint uppercase">
                  {plans.find((p) => p.slot === step.slot)?.label}
                </span>
              </div>
              <h2 className="m-0 mt-1 text-[24px] leading-tight font-semibold tracking-tight text-foreground sm:text-[26px]">{step.title}</h2>
              {step.hint && <p className="m-0 mt-1 text-sm leading-snug text-muted-foreground">{step.hint}</p>}
              <div className={cn('mt-5', picked !== null && 'pointer-events-none')}>{body[step.kind]()}</div>
            </motion.section>
          </AnimatePresence>
        </div>

        <button
          type="button"
          onClick={() => finish(true)}
          disabled={busy || arriving}
          className="mx-auto mt-2 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          Пропустить вопросы, подбирай как есть
        </button>
      </div>
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
  // kept here with the answers, so closed cards reopen on the same question
  const [position, setPosition] = useState<StepPosition>([0, 1])
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
          position={position}
          onPosition={setPosition}
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
