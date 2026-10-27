import type { ComponentType, SVGProps } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import {
  CalendarDaysIcon,
  CheckBadgeIcon,
  HeartIcon,
  MapIcon,
  PaperAirplaneIcon,
  SparklesIcon,
  UserGroupIcon,
  WalletIcon,
} from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { TripPassport } from '@/types/api'
import { ModeIcon } from '../components/LegRow'
import { passportChips, type ChipKind, type PassportField } from './passport'

const TrainIcon = ({ className }: SVGProps<SVGSVGElement>) => <ModeIcon mode="train" className={className} />

const ICONS: Record<ChipKind, ComponentType<SVGProps<SVGSVGElement>>> = {
  destination: MapIcon,
  when: CalendarDaysIcon,
  travelers: UserGroupIcon,
  budget: WalletIcon,
  origin: PaperAirplaneIcon,
  kinds: SparklesIcon,
  multi: MapIcon,
  visa: CheckBadgeIcon,
  land: TrainIcon,
  wish: HeartIcon,
}

interface PassportChipsProps {
  passport: TripPassport | null | undefined
  variant: 'cover' | 'cover-light' | 'compact'
  onEdit?: (field: PassportField) => void
  ghosts?: boolean
  max?: number
  className?: string
}

/** The trip as chips: they pop in as the agent understands the request, a changed one flashes. */
export function PassportChips({ passport, variant, onEdit, ghosts = true, max, className }: PassportChipsProps) {
  const chips = passportChips(passport, ghosts).slice(0, max)
  const compact = variant === 'compact'
  return (
    <motion.ul layout className={cn('m-0 flex list-none flex-wrap items-center p-0', compact ? 'gap-1' : 'gap-1.5', className)}>
      <AnimatePresence initial={false} mode="popLayout">
        {chips.map((chip, i) => {
          const Icon = ICONS[chip.kind]
          const editable = Boolean(chip.field && onEdit)
          // only a chip that edits something is a button: the compact header is a button itself
          const Tag = editable ? 'button' : 'span'
          return (
            <motion.li
              key={chip.key}
              layout
              initial={{ opacity: 0, y: 8, scale: 0.85 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8, transition: { duration: 0.15 } }}
              transition={{ type: 'spring', stiffness: 420, damping: 26, delay: Math.min(i, 6) * 0.04 }}
              className="list-none"
            >
              <Tag
                {...(editable ? { type: 'button' as const, onClick: () => chip.field && onEdit?.(chip.field) } : {})}
                title={editable ? (chip.ghost ? 'Подсказать агенту' : 'Изменить') : undefined}
                className={cn(
                  'group/chip relative inline-flex max-w-[16rem] items-center gap-1.5 overflow-hidden rounded-full font-medium whitespace-nowrap transition-[transform,background-color,box-shadow] duration-200',
                  compact ? 'px-2 py-0.5 text-[12px]' : 'px-2.5 py-1 text-[12.5px]',
                  editable && 'cursor-pointer hover:-translate-y-px active:translate-y-0',
                  chip.ghost
                    ? variant === 'cover'
                      ? 'border border-dashed border-white/70 bg-white/10 text-white/90 backdrop-blur-sm hover:bg-white/20'
                      : 'border border-dashed border-faintest bg-transparent text-faint hover:border-highlight/40 hover:text-highlight'
                    : variant === 'compact'
                      ? 'bg-secondary text-foreground hover:bg-accent'
                      : 'bg-white/90 text-foreground shadow-[0_4px_14px_-6px_rgba(15,23,42,0.35)] backdrop-blur-md hover:bg-white',
                )}
              >
                {/* a new or changed value sweeps once with light */}
                {!chip.ghost && !compact && (
                  <motion.span
                    aria-hidden
                    initial={{ x: '-120%' }}
                    animate={{ x: '220%' }}
                    transition={{ duration: 0.9, ease: 'easeInOut', delay: 0.15 }}
                    className="pointer-events-none absolute inset-y-0 left-0 w-1/2 bg-linear-to-r from-transparent via-primary/45 to-transparent"
                  />
                )}
                <Icon aria-hidden className={cn('relative h-3.5 w-3.5 shrink-0', chip.ghost ? 'opacity-80' : 'text-[#3f7d22]')} />
                <span className="relative truncate">{chip.text}</span>
              </Tag>
            </motion.li>
          )
        })}
      </AnimatePresence>
    </motion.ul>
  )
}
