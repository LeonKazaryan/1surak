import type { ReactNode } from 'react'
import { CheckCircleIcon, ExclamationTriangleIcon, InformationCircleIcon, StarIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { PlanCheck } from '@/types/api'
import { plural } from '../widgets'

interface PlanSectionProps {
  title: string
  children: ReactNode
  className?: string
}

/** One block of the plan, a named region so it reads as a landmark. */
export function PlanSection({ title, children, className }: PlanSectionProps) {
  return (
    <section aria-label={title} className={cn('flex flex-col gap-3 px-4 py-5 sm:px-6', className)}>
      <h4 className="m-0 text-xs font-semibold tracking-wider text-faint uppercase">{title}</h4>
      {children}
    </section>
  )
}

const LEVEL_ICON = { ok: CheckCircleIcon, info: InformationCircleIcon, warn: ExclamationTriangleIcon }
const LEVEL_TONE = { ok: 'text-[#4c9a2a]', info: 'text-highlight', warn: 'text-amber-500' }

export function CheckRow({ check }: { check: PlanCheck }) {
  const Icon = LEVEL_ICON[check.level]
  return (
    <li className="flex items-start gap-2.5">
      <Icon aria-hidden className={cn('mt-0.5 h-[18px] w-[18px] shrink-0', LEVEL_TONE[check.level])} />
      <span className="min-w-0">
        <span className="block text-[14px] leading-snug font-semibold text-foreground">{check.title}</span>
        <span className="block text-[13px] leading-snug text-muted-foreground">{check.text}</span>
        {check.fix && (
          <span className="mt-1.5 inline-flex rounded-full bg-accent px-2.5 py-0.5 text-[12px] font-medium text-foreground">
            {check.fix.label} можно добавить при оформлении
          </span>
        )}
      </span>
    </li>
  )
}

export function Stars({ count }: { count: number }) {
  return (
    <span role="img" aria-label={`${count} ${plural(count, ['звезда', 'звезды', 'звёзд'])}`} className="inline-flex text-amber-400">
      {Array.from({ length: count }, (_, i) => (
        <StarIcon key={i} aria-hidden className="h-3.5 w-3.5" />
      ))}
    </span>
  )
}
