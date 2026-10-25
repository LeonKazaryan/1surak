import { useId, useState, type ReactNode } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import { ArrowRightIcon, CheckIcon, MinusIcon, PlusIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { BriefAnswers, ClarifyEvent, ClarifySlot, TripKind } from '@/types/api'
import {
  BUDGET_OPTIONS,
  KIND_OPTIONS,
  NIGHT_OPTIONS,
  describeAnswers,
  nightsLabel,
  plural,
  upcomingMonths,
} from '../widgets'
import { TripArt } from './TripArt'

const SPRING = { type: 'spring', stiffness: 300, damping: 26 } as const
const list: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.15 } },
}
const item: Variants = {
  hidden: { opacity: 0, y: 22, scale: 0.97, filter: 'blur(6px)' },
  show: { opacity: 1, y: 0, scale: 1, filter: 'blur(0px)', transition: SPRING },
}
const MAX_ADULTS = 8
const MAX_CHILDREN = 5
const SLOT_NAMES: Record<ClarifySlot, string> = {
  vibe: 'тип отдыха',
  when: 'даты',
  travelers: 'кто едет',
  budget: 'бюджет',
}

interface ChoiceChipProps {
  selected: boolean
  onSelect: () => void
  pillId: string
  children: ReactNode
  className?: string
}

/** A chip whose highlight slides to the chosen option. */
function ChoiceChip({ selected, onSelect, pillId, children, className }: ChoiceChipProps) {
  return (
    <motion.button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      whileTap={{ scale: 0.95 }}
      className={cn(
        'relative min-h-10 rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
        selected ? 'border-transparent text-primary-foreground' : 'border-border bg-white text-foreground hover:border-highlight/30 hover:bg-accent/60',
        className,
      )}
    >
      {selected && (
        <motion.span
          layoutId={pillId}
          className="absolute inset-0 rounded-[11px] bg-primary shadow-[0_6px_16px_-8px_rgba(84,160,40,0.7)]"
          transition={{ type: 'spring', stiffness: 420, damping: 34 }}
        />
      )}
      <span className="relative">{children}</span>
    </motion.button>
  )
}

function CheckBadge({ className }: { className?: string }) {
  return (
    <motion.span
      initial={{ scale: 0, rotate: -45 }}
      animate={{ scale: 1, rotate: 0 }}
      exit={{ scale: 0 }}
      transition={{ type: 'spring', stiffness: 500, damping: 22 }}
      className={cn('flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground', className)}
    >
      <CheckIcon className="h-4 w-4" aria-hidden />
    </motion.span>
  )
}

function VibeQuestion({ kinds, onChange }: { kinds: TripKind[]; onChange: (kinds: TripKind[]) => void }) {
  const toggle = (kind: TripKind) =>
    onChange(kinds.includes(kind) ? kinds.filter((k) => k !== kind) : [...kinds, kind])
  return (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
      {KIND_OPTIONS.map(({ kind, label }) => {
        const selected = kinds.includes(kind)
        return (
          <motion.button
            key={kind}
            type="button"
            aria-pressed={selected}
            onClick={() => toggle(kind)}
            whileHover={{ y: -3 }}
            whileTap={{ scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            className={cn(
              'group relative overflow-hidden rounded-xl border bg-white text-left transition-[border-color,box-shadow] duration-200',
              selected
                ? 'border-highlight shadow-[0_0_0_3px_rgba(10,64,209,0.12),0_12px_24px_-16px_rgba(10,64,209,0.6)]'
                : 'border-border hover:shadow-[0_12px_24px_-18px_rgba(15,23,42,0.45)]',
            )}
          >
            <div className="h-20 overflow-hidden">
              <TripArt kind={kind} seed={`vibe-${kind}`} className="transition-transform duration-500 group-hover:scale-110" />
            </div>
            <span className="block px-3 py-2.5 text-[13px] font-semibold text-foreground">{label}</span>
            <AnimatePresence>{selected && <CheckBadge className="absolute top-2 right-2 shadow-md" />}</AnimatePresence>
          </motion.button>
        )
      })}
    </div>
  )
}

interface WhenQuestionProps {
  month: number | null
  nights: [number, number] | null
  nightOptions: [number, number][]
  onMonth: (month: number) => void
  onNights: (nights: [number, number]) => void
}

function WhenQuestion({ month, nights, nightOptions, onMonth, onNights }: WhenQuestionProps) {
  const id = useId()
  const months = upcomingMonths()
  const thisYear = months[0].year
  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="m-0 mb-2 text-xs font-semibold tracking-wider text-faint uppercase">Месяц</p>
        <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
          {months.map((m) => (
            <ChoiceChip key={`${m.year}-${m.month}`} selected={month === m.month} onSelect={() => onMonth(m.month)} pillId={`${id}-month`} className="flex flex-col items-center px-1 py-1.5 leading-tight">
              <span className="capitalize">{m.label}</span>
              {m.year !== thisYear && <span className="block text-[10px] font-normal opacity-60">{m.year}</span>}
            </ChoiceChip>
          ))}
        </div>
      </div>
      <div>
        <p className="m-0 mb-2 text-xs font-semibold tracking-wider text-faint uppercase">На сколько</p>
        <div className="flex flex-wrap gap-1.5">
          {nightOptions.map((option) => (
            <ChoiceChip
              key={option.join('-')}
              selected={nights?.[0] === option[0] && nights?.[1] === option[1]}
              onSelect={() => onNights(option)}
              pillId={`${id}-nights`}
            >
              {option[0] === option[1] ? `${option[0]} ${plural(option[0], ['ночь', 'ночи', 'ночей'])}` : nightsLabel(option)}
            </ChoiceChip>
          ))}
        </div>
      </div>
    </div>
  )
}

interface StepperProps {
  label: string
  hint: string
  value: number
  min: number
  max: number
  onChange: (value: number) => void
}

function Stepper({ label, hint, value, min, max, onChange }: StepperProps) {
  const button =
    'flex h-9 w-9 items-center justify-center rounded-full border border-border bg-white text-foreground transition-colors hover:border-highlight/40 hover:bg-accent disabled:opacity-35'
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-inset px-3.5 py-2.5">
      <div>
        <p className="m-0 text-sm font-semibold text-foreground">{label}</p>
        <p className="m-0 text-xs text-muted-foreground">{hint}</p>
      </div>
      <div className="flex items-center gap-2">
        <motion.button type="button" whileTap={{ scale: 0.88 }} className={button} onClick={() => onChange(value - 1)} disabled={value <= min} aria-label={`${label}: меньше`}>
          <MinusIcon className="h-4 w-4" />
        </motion.button>
        <span className="relative flex h-7 w-6 items-center justify-center overflow-hidden text-lg font-semibold text-foreground tabular-nums" aria-live="polite">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span key={value} initial={{ y: 14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -14, opacity: 0 }} transition={{ type: 'spring', stiffness: 500, damping: 30 }}>
              {value}
            </motion.span>
          </AnimatePresence>
        </span>
        <motion.button type="button" whileTap={{ scale: 0.88 }} className={button} onClick={() => onChange(value + 1)} disabled={value >= max} aria-label={`${label}: больше`}>
          <PlusIcon className="h-4 w-4" />
        </motion.button>
      </div>
    </div>
  )
}

interface TravelersQuestionProps {
  adults: number
  ages: (number | null)[]
  onAdults: (value: number) => void
  onAges: (ages: (number | null)[]) => void
}

function ageLabel(age: number): string {
  return age === 0 ? 'до 1 года' : `${age} ${plural(age, ['год', 'года', 'лет'])}`
}

function TravelersQuestion({ adults, ages, onAdults, onAges }: TravelersQuestionProps) {
  const setChildren = (count: number) =>
    onAges(count > ages.length ? [...ages, ...Array(count - ages.length).fill(null)] : ages.slice(0, count))
  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid gap-2.5 sm:grid-cols-2">
        <Stepper label="Взрослые" hint="от 18 лет" value={adults} min={1} max={MAX_ADULTS} onChange={onAdults} />
        <Stepper label="Дети" hint="до 17 лет" value={ages.length} min={0} max={MAX_CHILDREN} onChange={setChildren} />
      </div>
      <AnimatePresence initial={false}>
        {ages.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="overflow-hidden"
          >
            <div className="flex flex-wrap gap-2 pt-1">
              <AnimatePresence initial={false}>
                {ages.map((age, i) => (
                  <motion.label
                    key={i}
                    layout
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    className={cn(
                      'flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm transition-colors',
                      age === null ? 'border-highlight/40 bg-highlight/5' : 'border-border bg-white',
                    )}
                  >
                    <span className="text-muted-foreground">Ребёнок {ages.length > 1 ? i + 1 : ''}</span>
                    <select
                      value={age ?? ''}
                      onChange={(e) => onAges(ages.map((a, j) => (j === i ? Number(e.target.value) : a)))}
                      className="cursor-pointer rounded-md bg-transparent py-0.5 font-medium text-foreground outline-none"
                      aria-label={`Возраст ребёнка ${i + 1}`}
                    >
                      <option value="" disabled>
                        возраст?
                      </option>
                      {Array.from({ length: 18 }, (_, a) => (
                        <option key={a} value={a}>
                          {ageLabel(a)}
                        </option>
                      ))}
                    </select>
                  </motion.label>
                ))}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

interface BudgetQuestionProps {
  level: number | null
  total: number | null
  onLevel: (level: number) => void
  onTotal: (total: number | null) => void
}

function BudgetQuestion({ level, total, onLevel, onTotal }: BudgetQuestionProps) {
  const [custom, setCustom] = useState(total !== null)
  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 gap-2.5">
        {BUDGET_OPTIONS.map((option) => {
          const selected = level === option.level && !custom
          return (
            <motion.button
              key={option.level}
              type="button"
              aria-pressed={selected}
              onClick={() => {
                setCustom(false)
                onLevel(option.level)
              }}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.97 }}
              className={cn(
                'relative flex flex-col items-start gap-1 overflow-hidden rounded-xl border px-3.5 py-3 text-left transition-[border-color,background-color,box-shadow] duration-200',
                selected
                  ? 'border-highlight bg-highlight/4 shadow-[0_0_0_3px_rgba(10,64,209,0.12)]'
                  : 'border-border bg-white hover:bg-accent/50',
              )}
            >
              <span className="flex gap-0.5 text-[15px] leading-none font-bold" aria-hidden>
                {option.level
                  ? [1, 2, 3].map((n) => (
                      <span key={n} className={n <= option.level ? 'text-highlight' : 'text-faintest'}>
                        ₽
                      </span>
                    ))
                  : <span className="text-highlight">✦</span>}
              </span>
              <span className="text-sm font-semibold text-foreground">{option.label}</span>
              <span className="text-xs leading-snug text-muted-foreground">{option.hint}</span>
              <AnimatePresence>{selected && <CheckBadge className="absolute top-2.5 right-2.5 h-5 w-5" />}</AnimatePresence>
            </motion.button>
          )
        })}
      </div>
      <AnimatePresence initial={false} mode="wait">
        {custom ? (
          <motion.label
            key="input"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 rounded-xl border border-highlight/40 bg-white px-3.5 py-2.5 shadow-[0_0_0_3px_rgba(10,64,209,0.08)]"
          >
            <span className="text-sm text-muted-foreground">Сумма на всех</span>
            <input
              autoFocus
              inputMode="numeric"
              value={total ? total.toLocaleString('ru-RU') : ''}
              onChange={(e) => {
                const digits = Number(e.target.value.replace(/\D/g, '').slice(0, 9))
                onTotal(digits > 0 ? digits : null)
              }}
              placeholder="300 000"
              className="min-w-0 flex-1 bg-transparent text-right text-[15px] font-semibold text-foreground outline-none placeholder:font-normal placeholder:text-faint"
              aria-label="Бюджет на всех, рублей"
            />
            <span className="text-sm font-semibold text-foreground">₽</span>
          </motion.label>
        ) : (
          <motion.button
            key="toggle"
            type="button"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => {
              setCustom(true)
              onTotal(null)
            }}
            className="self-start text-[13px] font-medium text-highlight underline-offset-4 hover:underline"
          >
            Указать свою сумму
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  )
}

interface QuestionCardProps {
  index: number
  title: string
  hint?: string | null
  answered: boolean
  children: ReactNode
}

function QuestionCard({ index, title, hint, answered, children }: QuestionCardProps) {
  return (
    <motion.section
      variants={item}
      className={cn(
        'rounded-2xl border bg-card p-4 transition-[border-color,box-shadow] duration-300 sm:p-5',
        answered ? 'border-primary/70 shadow-[0_14px_36px_-26px_rgba(84,160,40,0.55)]' : 'border-border shadow-[0_14px_36px_-28px_rgba(15,23,42,0.35)]',
      )}
    >
      <header className="mb-4 flex items-start gap-3">
        <span className="relative flex h-7 w-7 shrink-0 items-center justify-center">
          <AnimatePresence initial={false} mode="popLayout">
            {answered ? (
              <CheckBadge key="done" className="h-7 w-7" />
            ) : (
              <motion.span
                key="num"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
                className="flex h-7 w-7 items-center justify-center rounded-full bg-highlight text-[13px] font-semibold text-white tabular-nums"
              >
                {index + 1}
              </motion.span>
            )}
          </AnimatePresence>
        </span>
        <div className="min-w-0 pt-0.5">
          <h3 className="m-0 text-base leading-snug font-semibold tracking-tight text-foreground">{title}</h3>
          {hint && <p className="m-0 mt-0.5 text-[13px] leading-snug text-muted-foreground">{hint}</p>}
        </div>
      </header>
      {children}
    </motion.section>
  )
}

interface ClarifyCardsProps {
  widget: ClarifyEvent
  /** Only the latest questions take input; older ones show as answered. */
  active: boolean
  /** The agent is still finishing this turn: answers can be picked but not sent yet. */
  busy: boolean
  onSubmit: (text: string, answers: BriefAnswers) => void
}

/** The questions the agent still needs, as cards with ready answers to tap, sent back in one message. */
export function ClarifyCards({ widget, active, busy, onSubmit }: ClarifyCardsProps) {
  const { questions, prefill } = widget
  const [kinds, setKinds] = useState<TripKind[]>(prefill.kinds)
  const [month, setMonth] = useState<number | null>(prefill.month)
  const [nights, setNights] = useState<[number, number] | null>(prefill.nights)
  const [adults, setAdults] = useState(prefill.adults ?? 2)
  const [ages, setAges] = useState<(number | null)[]>(() =>
    Array.from({ length: prefill.children ?? 0 }, (_, i) => prefill.children_ages[i] ?? null),
  )
  const [level, setLevel] = useState<number | null>(prefill.budget_level)
  const [total, setTotal] = useState<number | null>(null)
  const [sent, setSent] = useState(false)

  const nightOptions =
    prefill.nights && !NIGHT_OPTIONS.some((o) => o[0] === prefill.nights![0] && o[1] === prefill.nights![1])
      ? [prefill.nights, ...NIGHT_OPTIONS]
      : NIGHT_OPTIONS
  const answered: Record<ClarifySlot, boolean> = {
    vibe: kinds.length > 0,
    when: month !== null && nights !== null,
    travelers: adults >= 1 && ages.every((a) => a !== null),
    budget: total !== null || level !== null,
  }
  const doneCount = questions.filter((q) => answered[q.slot]).length
  const allDone = doneCount === questions.length
  const canSend = allDone && !busy

  const collect = (): BriefAnswers => {
    const answers: BriefAnswers = {}
    const asked = new Set(questions.map((q) => q.slot))
    if (asked.has('vibe') && answered.vibe) answers.kinds = kinds
    if (asked.has('when')) {
      if (month !== null) answers.month = month
      if (nights) [answers.nights_min, answers.nights_max] = nights
    }
    if (asked.has('travelers') && answered.travelers) {
      answers.adults = adults
      answers.children = ages.length
      answers.children_ages = ages as number[]
    }
    if (asked.has('budget')) {
      if (total !== null) answers.budget_total_rub = total
      else if (level !== null) answers.budget_level = level
    }
    return answers
  }

  const submit = (skipRest = false) => {
    const answers = collect()
    const text = describeAnswers(answers)
    setSent(true)
    onSubmit(skipRest ? (text ? `${text}. Остальное не важно, подбирай` : 'Подбирай без уточнений') : text, answers)
  }

  // Distinct keys: both states are a motion.div, and reusing one would skip the cards' entrance.
  if (!active || sent) {
    return (
      <motion.div
        key="answered"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-3 flex items-center gap-2.5 rounded-xl border border-border bg-card px-3.5 py-2.5 text-[13px] text-muted-foreground"
      >
        <CheckBadge className="h-5 w-5" />
        <span>Уточнили: {questions.map((q) => SLOT_NAMES[q.slot]).join(', ')}</span>
      </motion.div>
    )
  }

  const cards: Record<ClarifySlot, ReactNode> = {
    vibe: <VibeQuestion kinds={kinds} onChange={setKinds} />,
    when: <WhenQuestion month={month} nights={nights} nightOptions={nightOptions} onMonth={setMonth} onNights={setNights} />,
    travelers: <TravelersQuestion adults={adults} ages={ages} onAdults={setAdults} onAges={setAges} />,
    budget: (
      <BudgetQuestion
        level={level}
        total={total}
        onLevel={(value) => {
          setLevel(value)
          setTotal(null)
        }}
        onTotal={(value) => {
          setTotal(value)
          setLevel(null)
        }}
      />
    ),
  }

  return (
    <motion.div key="questions" variants={list} initial="hidden" animate="show" className="mt-4 flex flex-col gap-3">
      {questions.map((q, i) => (
        <QuestionCard key={q.slot} index={i} title={q.title} hint={q.hint} answered={answered[q.slot]}>
          {cards[q.slot]}
        </QuestionCard>
      ))}
      <motion.div variants={item} className="flex flex-wrap items-center gap-3 pt-1">
        <div className="flex min-w-[9rem] flex-1 items-center gap-2.5">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
            <motion.div
              className="h-full rounded-full bg-primary"
              initial={false}
              animate={{ width: `${(doneCount / questions.length) * 100}%` }}
              transition={{ type: 'spring', stiffness: 200, damping: 26 }}
            />
          </div>
          <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">
            {doneCount} из {questions.length}
          </span>
        </div>
        {!allDone && (
          <button
            type="button"
            onClick={() => submit(true)}
            disabled={busy}
            className="text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Пропустить
          </button>
        )}
        <motion.button
          type="button"
          onClick={() => submit()}
          disabled={!canSend}
          whileHover={canSend ? { scale: 1.03 } : undefined}
          whileTap={canSend ? { scale: 0.97 } : undefined}
          className={cn(
            'inline-flex h-11 items-center gap-2 rounded-full px-5 text-[15px] font-semibold transition-[background-color,color,box-shadow] duration-300',
            canSend
              ? 'bg-primary text-primary-foreground shadow-[0_10px_24px_-12px_rgba(84,160,40,0.8)] hover:bg-primary-hover'
              : 'bg-secondary text-faint',
          )}
        >
          Подобрать направления
          <ArrowRightIcon className="h-4 w-4" aria-hidden />
        </motion.button>
      </motion.div>
    </motion.div>
  )
}
