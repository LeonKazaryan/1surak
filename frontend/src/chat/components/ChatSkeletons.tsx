import type { CSSProperties } from 'react'
import { Skeleton } from '@/components/ui/skeleton'

const RECENT_ROW_WIDTHS = ['78%', '62%', '70%', '54%']

function fade(step: number): CSSProperties {
  return { opacity: 1 - step * 0.2 }
}

export function RecentChatsSkeleton() {
  return (
    <div data-testid="recent-chats-skeleton" aria-hidden className="skeleton-reveal flex flex-col gap-1">
      {RECENT_ROW_WIDTHS.map((width, i) => (
        <div key={i} className="flex h-8 items-center px-2" style={fade(i)}>
          <Skeleton className="h-3.5" style={{ width }} />
        </div>
      ))}
    </div>
  )
}

export function MessagesSkeleton() {
  return (
    <div data-testid="messages-skeleton" aria-hidden className="skeleton-reveal flex h-full flex-col justify-end pt-4 pb-6">
      <div className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-6 max-md:px-4">
        {[2, 0].map((step) => (
          <div key={step} className="flex flex-col gap-6" style={fade(step)}>
            <div className="flex justify-end">
              <Skeleton className="h-11 w-[42%] rounded-2xl" />
            </div>
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <Skeleton className="h-7 w-7 rounded-lg" />
                <Skeleton className="h-3.5 w-32" />
              </div>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-[88%]" />
              <Skeleton className="h-4 w-[56%]" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
