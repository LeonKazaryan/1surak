import { useId, useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { AnimatePresence, motion, type Variants } from 'motion/react'
import { ArrowRightIcon, CheckIcon, FaceSmileIcon, UserGroupIcon, UserIcon, UsersIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { TripKind } from '@/types/api'
import { TripArt } from '../components/TripArt'
import { BUDGET_OPTIONS, KIND_OPTIONS, NIGHT_OPTIONS, nightsLabel, plural, upcomingMonths } from '../widgets'
import type { Party } from './plan'

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
const PARTIES: Record<Party, { icon: ComponentType<SVGProps<SVGSVGElement>>; label: string; sub: string }> = {
  solo: { icon: UserIcon, label: 'Один', sub: '1 взрослый' },
  couple: { icon: UsersIcon, label: 'Вдвоём', sub: '2 взрослых' },
  kids: { icon: FaceSmileIcon, label: 'С детьми', sub: 'спрошу возраст' },
  group: { icon: UserGroupIcon, label: 'Компанией', sub: '3 и больше' },
  oneAdult: { icon: UserIcon, label: 'Я с детьми', sub: 'один взрослый' },
  twoAdults: { icon: UsersIcon, label: 'Вдвоём с детьми', sub: 'двое взрослых' },
}

/** Options fall into place one after another once the card has landed. */
const options: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04, delayChildren: 0.12 } },
}
const option: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 420, damping: 28 } },
}

function Options({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <motion.div variants={options} initial="hidden" animate="show" className={className}>
      {children}
    </motion.div>
  )
}

function CheckBadge({ className }: { className?: string }) {
  return (
    <motion.span
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      transition={{ type: 'spring', stiffness: 520, damping: 22 }}
      className={cn('flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground', className)}
    >
      <CheckIcon className="h-4 w-4" aria-hidden />
    </motion.span>
  )
}

interface ChipProps {
  selected: boolean
  onPick: () => void
  pillId: string
  children: ReactNode
  className?: string
  label?: string
}

/** A tap target whose lime highlight slides over to the picked option. */
function Chip({ selected, onPick, pillId, children, className, label }: ChipProps) {
  return (
    <motion.button
      type="button"
      variants={option}
      aria-pressed={selected}
      aria-label={label}
      onClick={onPick}
      whileTap={{ scale: 0.94 }}
      className={cn(
        'relative min-h-12 rounded-2xl border px-3 py-2 text-[15px] font-medium transition-colors',
        selected ? 'border-transparent text-primary-foreground' : 'border-border bg-white text-foreground hover:border-highlight/30 hover:bg-accent/60',
        className,
      )}
    >
      {selected && (
        <motion.span layoutId={pillId} className="absolute inset-0 rounded-[15px] bg-primary" transition={{ type: 'spring', stiffness: 460, damping: 34 }} />
      )}
      <span className="relative">{children}</span>
    </motion.button>
  )
}

interface PickProps<T> {
  selected: T | null
  onPick: (value: T) => void
}

export function VibeStep({ selected, onPick }: PickProps<TripKind>) {
  return (
    <Options className="grid grid-cols-2 gap-2.5 sm:grid-cols-6">
      {KIND_OPTIONS.map(({ kind, label }) => (
        <motion.button
          key={kind}
          type="button"
          variants={option}
          aria-pressed={selected === kind}
          aria-label={label}
          onClick={() => onPick(kind)}
          whileHover={{ y: -3 }}
          whileTap={{ scale: 0.97 }}
          className={cn(
            'group relative overflow-hidden rounded-2xl text-left ring-offset-2 ring-offset-card',
            VIBE_LAYOUT[kind],
            selected === kind && 'ring-[3px] ring-highlight',
          )}
        >
          <TripArt kind={kind} seed={`vibe-${kind}`} still className="absolute inset-0 transition-transform duration-500 ease-out group-hover:scale-105" />
          <span className="absolute inset-0 bg-linear-to-t from-slate-950/65 via-slate-950/10 to-transparent" />
          <span className="absolute right-3 bottom-2.5 left-3">
            <span className="block text-[15px] leading-tight font-semibold text-white">{label}</span>
            <span className="block text-[12px] text-white/80">{VIBE_TAGLINES[kind]}</span>
          </span>
          {selected === kind && <CheckBadge className="absolute top-2.5 right-2.5" />}
        </motion.button>
      ))}
    </Options>
  )
}

export function MonthStep({ selected, onPick }: PickProps<number>) {
  const id = useId()
  const months = upcomingMonths()
  const thisYear = months[0].year
  return (
    <Options className="grid grid-cols-4 gap-2 sm:grid-cols-6">
      {months.map((m) => (
        <Chip
          key={`${m.year}-${m.month}`}
          selected={selected === m.month}
          onPick={() => onPick(m.month)}
          pillId={`${id}-month`}
          className="flex flex-col items-center px-1 py-2 leading-tight"
        >
          <span className="capitalize">{m.label}</span>
          {m.year !== thisYear && <span className="block text-[10px] font-normal opacity-60">{m.year}</span>}
        </Chip>
      ))}
    </Options>
  )
}

export function NightsStep({ selected, onPick, extra }: PickProps<[number, number]> & { extra?: [number, number] | null }) {
  const id = useId()
  const list = extra && !NIGHT_OPTIONS.some((o) => o.join() === extra.join()) ? [extra, ...NIGHT_OPTIONS] : NIGHT_OPTIONS
  return (
    <Options className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {list.map((o) => (
        <Chip key={o.join('-')} selected={selected?.join() === o.join()} onPick={() => onPick(o)} pillId={`${id}-nights`} className="py-3">
          {nightsLabel(o)}
        </Chip>
      ))}
    </Options>
  )
}

export function PartyStep({ choices, selected, onPick }: PickProps<Party> & { choices: Party[] }) {
  return (
    <Options className="grid grid-cols-2 gap-2.5">
      {choices.map((party) => {
        const { icon: Icon, label, sub } = PARTIES[party]
        const on = selected === party
        return (
          <motion.button
            key={party}
            type="button"
            variants={option}
            aria-pressed={on}
            aria-label={label}
            onClick={() => onPick(party)}
            whileHover={{ y: -3 }}
            whileTap={{ scale: 0.96 }}
            className={cn(
              'relative flex flex-col items-start gap-2 rounded-2xl border p-4 text-left transition-colors',
              on ? 'border-highlight bg-highlight/5' : 'border-border bg-white hover:bg-accent/50',
            )}
          >
            <span className={cn('flex h-10 w-10 items-center justify-center rounded-xl', on ? 'bg-highlight text-white' : 'bg-accent text-highlight')}>
              <Icon className="h-5 w-5" aria-hidden />
            </span>
            <span>
              <span className="block text-base font-semibold text-foreground">{label}</span>
              <span className="block text-[13px] text-muted-foreground">{sub}</span>
            </span>
            {on && <CheckBadge className="absolute top-3 right-3 h-5 w-5" />}
          </motion.button>
        )
      })}
    </Options>
  )
}

export function CountStep({ values, selected, onPick, unit }: PickProps<number> & { values: number[]; unit: [string, string, string] }) {
  const id = useId()
  return (
    <Options className="flex flex-wrap gap-2.5">
      {values.map((n) => (
        <Chip
          key={n}
          selected={selected === n}
          onPick={() => onPick(n)}
          pillId={`${id}-count`}
          label={`${n} ${plural(n, unit)}`}
          className="flex h-16 w-16 flex-col items-center justify-center p-0 leading-none"
        >
          <span className="text-xl font-semibold">{n}</span>
        </Chip>
      ))}
    </Options>
  )
}

export function AgeStep({ selected, onPick }: PickProps<number>) {
  const id = useId()
  return (
    <Options className="grid grid-cols-6 gap-2">
      {Array.from({ length: 18 }, (_, age) => (
        <Chip
          key={age}
          selected={selected === age}
          onPick={() => onPick(age)}
          pillId={`${id}-age`}
          label={age === 0 ? 'до 1 года' : `${age} ${plural(age, ['год', 'года', 'лет'])}`}
          className="px-0 text-base font-semibold"
        >
          {age === 0 ? '<1' : age}
        </Chip>
      ))}
    </Options>
  )
}

interface BudgetStepProps {
  level: number | null
  onLevel: (level: number) => void
  onTotal: (total: number) => void
}

export function BudgetStep({ level, onLevel, onTotal }: BudgetStepProps) {
  const [custom, setCustom] = useState(false)
  const [draft, setDraft] = useState<number | null>(null)
  const send = () => draft && onTotal(draft)
  return (
    <Options className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 gap-2.5">
        {BUDGET_OPTIONS.map((o) => {
          const on = level === o.level && !custom
          return (
            <motion.button
              key={o.level}
              type="button"
              variants={option}
              aria-pressed={on}
              onClick={() => onLevel(o.level)}
              whileHover={{ y: -3 }}
              whileTap={{ scale: 0.96 }}
              className={cn(
                'relative flex flex-col items-start gap-1 rounded-2xl border px-4 py-3.5 text-left transition-colors',
                on ? 'border-highlight bg-highlight/5' : 'border-border bg-white hover:bg-accent/50',
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
              {on && <CheckBadge className="absolute top-3 right-3 h-5 w-5" />}
            </motion.button>
          )
        })}
      </div>
      <AnimatePresence initial={false} mode="wait">
        {custom ? (
          <motion.form
            key="sum"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
            className="flex items-center gap-2 rounded-2xl border border-highlight/40 bg-white py-1.5 pr-1.5 pl-4"
          >
            <span className="text-sm text-muted-foreground">Сумма на всех</span>
            <input
              autoFocus
              inputMode="numeric"
              value={draft ? draft.toLocaleString('ru-RU') : ''}
              onChange={(e) => {
                const digits = Number(e.target.value.replace(/\D/g, '').slice(0, 9))
                setDraft(digits > 0 ? digits : null)
              }}
              placeholder="300 000"
              className="min-w-0 flex-1 bg-transparent text-right text-base font-semibold text-foreground outline-none placeholder:font-normal placeholder:text-faint"
              aria-label="Бюджет на всех, рублей"
            />
            <span className="text-sm font-semibold text-foreground">₽</span>
            <button
              type="submit"
              disabled={!draft}
              aria-label="Готово"
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-colors hover:bg-primary-hover disabled:bg-secondary disabled:text-faint"
            >
              <ArrowRightIcon className="h-4 w-4" />
            </button>
          </motion.form>
        ) : (
          <motion.button
            key="toggle"
            type="button"
            variants={option}
            onClick={() => setCustom(true)}
            className="self-start text-[13px] font-medium text-highlight underline-offset-4 hover:underline"
          >
            Указать свою сумму
          </motion.button>
        )}
      </AnimatePresence>
    </Options>
  )
}
