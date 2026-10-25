import { ArrowPathIcon, ClockIcon } from '@heroicons/react/20/solid'
import { Button } from '@/components/ui/button'
import { cn } from '@/components/ui/utils'
import type { TripStatus } from '@/types/api'
import { shortDate } from './ticketFormat'

interface TripFreshnessProps {
  status: Partial<TripStatus>
  refreshing: boolean
  onRefresh: () => void
  onNewDates: () => void
}

/** A saved trip that no longer holds: old tickets get one tap to refresh, past dates ask for new ones. */
export function TripFreshness({ status, refreshing, onRefresh, onNewDates }: TripFreshnessProps) {
  const passed = Boolean(status.dates_passed)
  if (!passed && !(status.stale && status.priced_at)) return null
  return (
    <div
      role="status"
      className="mb-2 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 py-1.5 pr-1.5 pl-3 text-[13px] text-amber-900"
    >
      <ClockIcon className="h-4 w-4 shrink-0 text-amber-600" aria-hidden />
      <span className="min-w-0 flex-1">
        {passed ? 'Даты поездки уже прошли' : `Цены от ${shortDate(status.priced_at ?? '')} могли измениться`}
      </span>
      {passed ? (
        <Button variant="outline" size="sm" onClick={onNewDates} className="shrink-0 rounded-lg bg-card">
          Выбрать новые даты
        </Button>
      ) : (
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={refreshing} className="shrink-0 rounded-lg bg-card">
          <ArrowPathIcon className={cn(refreshing && 'animate-spin motion-reduce:animate-none')} aria-hidden />
          {refreshing ? 'Обновляю' : 'Обновить цены'}
        </Button>
      )}
    </div>
  )
}
