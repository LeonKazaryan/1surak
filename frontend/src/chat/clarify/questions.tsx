import { useId, useState, type ReactNode } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import { CheckIcon, MinusIcon, PlusIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { TripKind } from '@/types/api'
import { TripArt } from '../components/TripArt'
import { BUDGET_OPTIONS, KIND_OPTIONS, nightsLabel, plural, upcomingMonths } from '../widgets'

const MAX_ADULTS = 8
const MAX_CHILDREN = 5
const VIBE_TAGLINES: Record<TripKind, string> = {
  sea: 'тёплая вода и песок',
  mountains: 'виды и тропы',
  city: 'экскурсии и еда',
  nature: 'тишина и воздух',
  ski: 'склоны и снег',
}
// Bento: the two big scenes on top, three below; on phones two per row and skiing full width.
const VIBE_LAYOUT: Record<TripKind, string> = {
  sea: 'col-span-1 sm:col-span-3 h-32 sm:h-36',
  mountains: 'col-span-1 sm:col-span-3 h-32 sm:h-36',
  city: 'col-span-1 sm:col-span-2 h-28',
  nature: 'col-span-1 sm:col-span-2 h-28',
  ski: 'col-span-2 sm:col-span-2 h-28',
}

/** Options inside a card fall into place one after another once the card has landed. */
const options: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.045, delayChildren: 0.18 } },
}
const option: Variants = {
  hidden: { opacity: 0, y: 12, scale: 0.96 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: 'spring', stiffness: 380, damping: 26 } },
}

export function CheckBadge({ className }: { className?: string }) {
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
      variants={option}
      aria-pressed={selected}
      onClick={onSelect}
      whileTap={{ scale: 0.94 }}
      className={cn(
        'relative min-h-11 rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
        selected
          ? 'border-transparent text-primary-foreground'
          : 'border-border bg-white text-foreground hover:border-highlight/30 hover:bg-accent/60',
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

export function VibeQuestion({ kinds, onChange }: { kinds: TripKind[]; onChange: (kinds: TripKind[]) => void }) {
  const toggle = (kind: TripKind) => onChange(kinds.includes(kind) ? kinds.filter((k) => k !== kind) : [...kinds, kind])
  return (
    <motion.div variants={options} initial="hidden" animate="show" className="grid grid-cols-2 gap-2.5 sm:grid-cols-6">
      {KIND_OPTIONS.map(({ kind, label }) => {
        const selected = kinds.includes(kind)
        return (
          <motion.button
            key={kind}
            type="button"
            variants={option}
            aria-pressed={selected}
            aria-label={label}
            onClick={() => toggle(kind)}
            whileHover={{ y: -4 }}
            whileTap={{ scale: 0.97 }}
            className={cn(
              'group relative overflow-hidden rounded-2xl text-left ring-offset-2 ring-offset-card transition-[box-shadow] duration-200',
              VIBE_LAYOUT[kind],
              selected
                ? 'ring-[3px] ring-highlight shadow-[0_18px_30px_-18px_rgba(10,64,209,0.7)]'
                : 'shadow-[0_12px_24px_-20px_rgba(15,23,42,0.6)]',
            )}
          >
            <TripArt kind={kind} seed={`vibe-${kind}`} className="absolute inset-0 transition-transform duration-700 ease-out group-hover:scale-110" />
            <span className="absolute inset-0 bg-linear-to-t from-slate-950/65 via-slate-950/10 to-transparent" />
            <span className="absolute right-3 bottom-2.5 left-3">
              <span className="block text-[15px] leading-tight font-semibold text-white drop-shadow">{label}</span>
              <span className="block text-[12px] text-white/80">{VIBE_TAGLINES[kind]}</span>
            </span>
            <AnimatePresence>{selected && <CheckBadge className="absolute top-2.5 right-2.5 shadow-md" />}</AnimatePresence>
          </motion.button>
        )
      })}
    </motion.div>
  )
}

interface WhenQuestionProps {
  askMonth: boolean
  askNights: boolean
  month: number | null
  nights: [number, number] | null
  nightOptions: [number, number][]
  onMonth: (month: number) => void
  onNights: (nights: [number, number]) => void
}

export function WhenQuestion({ askMonth, askNights, month, nights, nightOptions, onMonth, onNights }: WhenQuestionProps) {
  const id = useId()
  const months = upcomingMonths()
  const thisYear = months[0].year
  return (
    <motion.div variants={options} initial="hidden" animate="show" className="flex flex-col gap-5">
      {askMonth && (
        <div>
          {askNights && <p className="m-0 mb-2 text-xs font-semibold tracking-wider text-faint uppercase">Месяц</p>}
          <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
            {months.map((m) => (
              <ChoiceChip
                key={`${m.year}-${m.month}`}
                selected={month === m.month}
                onSelect={() => onMonth(m.month)}
                pillId={`${id}-month`}
                className="flex flex-col items-center px-1 py-1.5 leading-tight"
              >
                <span className="capitalize">{m.label}</span>
                {m.year !== thisYear && <span className="block text-[10px] font-normal opacity-60">{m.year}</span>}
              </ChoiceChip>
            ))}
          </div>
        </div>
      )}
      {askNights && (
        <div>
          {askMonth && <p className="m-0 mb-2 text-xs font-semibold tracking-wider text-faint uppercase">На сколько</p>}
          <div className="flex flex-wrap gap-1.5">
            {nightOptions.map((o) => (
              <ChoiceChip
                key={o.join('-')}
                selected={nights?.[0] === o[0] && nights?.[1] === o[1]}
                onSelect={() => onNights(o)}
                pillId={`${id}-nights`}
                className="px-4"
              >
                {nightsLabel(o)}
              </ChoiceChip>
            ))}
          </div>
        </div>
      )}
    </motion.div>
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
    'flex h-10 w-10 items-center justify-center rounded-full border border-border bg-white text-foreground transition-colors hover:border-highlight/40 hover:bg-accent disabled:opacity-35'
  return (
    <motion.div variants={option} className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-inset px-4 py-3">
      <div>
        <p className="m-0 text-[15px] font-semibold text-foreground">{label}</p>
        <p className="m-0 text-xs text-muted-foreground">{hint}</p>
      </div>
      <div className="flex items-center gap-2">
        <motion.button type="button" whileTap={{ scale: 0.88 }} className={button} onClick={() => onChange(value - 1)} disabled={value <= min} aria-label={`${label}: меньше`}>
          <MinusIcon className="h-4 w-4" />
        </motion.button>
        <span className="relative flex h-8 w-7 items-center justify-center overflow-hidden text-xl font-semibold text-foreground tabular-nums" aria-live="polite">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span
              key={value}
              initial={{ y: 16, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -16, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 500, damping: 30 }}
            >
              {value}
            </motion.span>
          </AnimatePresence>
        </span>
        <motion.button type="button" whileTap={{ scale: 0.88 }} className={button} onClick={() => onChange(value + 1)} disabled={value >= max} aria-label={`${label}: больше`}>
          <PlusIcon className="h-4 w-4" />
        </motion.button>
      </div>
    </motion.div>
  )
}

function ageLabel(age: number): string {
  return age === 0 ? 'до 1 года' : `${age} ${plural(age, ['год', 'года', 'лет'])}`
}

interface TravelersQuestionProps {
  askCounts: boolean
  adults: number
  ages: (number | null)[]
  onAdults: (value: number) => void
  onAges: (ages: (number | null)[]) => void
}

export function TravelersQuestion({ askCounts, adults, ages, onAdults, onAges }: TravelersQuestionProps) {
  const setChildren = (count: number) =>
    onAges(count > ages.length ? [...ages, ...Array(count - ages.length).fill(null)] : ages.slice(0, count))
  return (
    <motion.div variants={options} initial="hidden" animate="show" className="flex flex-col gap-2.5">
      {askCounts && (
        <div className="grid gap-2.5 sm:grid-cols-2">
          <Stepper label="Взрослые" hint="от 18 лет" value={adults} min={1} max={MAX_ADULTS} onChange={onAdults} />
          <Stepper label="Дети" hint="до 17 лет" value={ages.length} min={0} max={MAX_CHILDREN} onChange={setChildren} />
        </div>
      )}
      <AnimatePresence initial={false}>
        {ages.length > 0 && (
          <motion.div
            initial={askCounts ? { height: 0, opacity: 0 } : false}
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
                    variants={option}
                    exit={{ opacity: 0, scale: 0.9 }}
                    className={cn(
                      'flex min-h-11 items-center gap-2 rounded-xl border px-3.5 py-2 text-sm transition-colors',
                      age === null ? 'border-highlight/40 bg-highlight/5' : 'border-primary bg-accent',
                    )}
                  >
                    <span className="text-muted-foreground">Ребёнок {ages.length > 1 ? i + 1 : ''}</span>
                    <select
                      value={age ?? ''}
                      onChange={(e) => onAges(ages.map((a, j) => (j === i ? Number(e.target.value) : a)))}
                      className="cursor-pointer rounded-md bg-transparent py-0.5 font-semibold text-foreground outline-none"
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
    </motion.div>
  )
}

interface BudgetQuestionProps {
  level: number | null
  total: number | null
  onLevel: (level: number) => void
  onTotal: (total: number | null) => void
}

export function BudgetQuestion({ level, total, onLevel, onTotal }: BudgetQuestionProps) {
  const [custom, setCustom] = useState(total !== null)
  return (
    <motion.div variants={options} initial="hidden" animate="show" className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 gap-2.5">
        {BUDGET_OPTIONS.map((o) => {
          const selected = level === o.level && !custom
          return (
            <motion.button
              key={o.level}
              type="button"
              variants={option}
              aria-pressed={selected}
              onClick={() => {
                setCustom(false)
                onLevel(o.level)
              }}
              whileHover={{ y: -3 }}
              whileTap={{ scale: 0.97 }}
              className={cn(
                'relative flex flex-col items-start gap-1 overflow-hidden rounded-2xl border px-4 py-3.5 text-left transition-[border-color,background-color,box-shadow] duration-200',
                selected
                  ? 'border-highlight bg-highlight/4 shadow-[0_0_0_3px_rgba(10,64,209,0.12)]'
                  : 'border-border bg-white hover:bg-accent/50',
              )}
            >
              <span className="flex gap-0.5 text-base leading-none font-bold" aria-hidden>
                {o.level ? (
                  [1, 2, 3].map((n) => (
                    <span key={n} className={n <= o.level ? 'text-highlight' : 'text-faintest'}>
                      ₽
                    </span>
                  ))
                ) : (
                  <span className="text-highlight">✦</span>
                )}
              </span>
              <span className="text-[15px] font-semibold text-foreground">{o.label}</span>
              <span className="text-xs leading-snug text-muted-foreground">{o.hint}</span>
              <AnimatePresence>{selected && <CheckBadge className="absolute top-3 right-3 h-5 w-5" />}</AnimatePresence>
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
            className="flex items-center gap-2 rounded-2xl border border-highlight/40 bg-white px-4 py-3 shadow-[0_0_0_3px_rgba(10,64,209,0.08)]"
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
              className="min-w-0 flex-1 bg-transparent text-right text-base font-semibold text-foreground outline-none placeholder:font-normal placeholder:text-faint"
              aria-label="Бюджет на всех, рублей"
            />
            <span className="text-sm font-semibold text-foreground">₽</span>
          </motion.label>
        ) : (
          <motion.button
            key="toggle"
            type="button"
            variants={option}
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
    </motion.div>
  )
}
