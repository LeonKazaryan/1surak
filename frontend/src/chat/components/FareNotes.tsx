import { useContext } from 'react'
import { motion } from 'motion/react'
import { ArrowTopRightOnSquareIcon, ArrowTrendingUpIcon, MagnifyingGlassIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import { CurrencyContext, formatMoney } from '../widgets'
import { shortDate } from './ticketFormat'

interface LiveSearchLinkProps {
  href: string
  /** The day the plan has the flight on: the search opens on it. */
  day?: string | null
  from: string
  to: string
  className?: string
}

/** The live search on Aviasales for a day its cache has no fare for: every fare of the day is there. */
export function LiveSearchLink({ href, day, from, to, className }: LiveSearchLinkProps) {
  const label = day ? `Цены на ${shortDate(day)} в Aviasales` : 'Цены в поиске Aviasales'
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`${label}: ${from} → ${to}`}
      className={cn(
        'group mt-1.5 inline-flex h-7 items-center gap-1 rounded-full bg-highlight/10 px-2.5 text-[12px] font-medium text-highlight transition-colors hover:bg-highlight/20',
        className,
      )}
    >
      <MagnifyingGlassIcon className="h-3.5 w-3.5 transition-transform group-hover:-rotate-12" aria-hidden />
      {label}
      <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5" aria-hidden />
    </a>
  )
}

/** A ticket on the plan's dates that costs clearly more than the route usually does: the usual fare next to it. */
export function DearTag({ usual, compact = false }: { usual: number; compact?: boolean }) {
  const currency = useContext(CurrencyContext)
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 480, damping: 22, delay: 0.45 }}
      title={`Лучший билет на эти даты, но обычно на этом направлении около ${formatMoney(usual, currency)}`}
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-amber-50 font-medium whitespace-nowrap text-amber-800 ring-1 ring-amber-200',
        compact ? 'px-1.5 text-[10px]' : 'px-2 py-0.5 text-[11px]',
      )}
    >
      <ArrowTrendingUpIcon className={compact ? 'h-2.5 w-2.5' : 'h-3 w-3'} aria-hidden />
      {compact ? 'дороже обычного' : `дороже обычного · обычно ~${formatMoney(usual, currency)}`}
    </motion.span>
  )
}
