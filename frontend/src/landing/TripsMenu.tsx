import { useContext } from 'react'
import { ArrowRightIcon, ArrowUpRightIcon } from '@heroicons/react/20/solid'
import { CardNavGoContext } from '@/components/cardNavGo'
import { useIsMobile } from '@/hooks/use-mobile'
import { cn } from '@/components/ui/utils'
import type { ChatMeta } from '@/types/api'

const UNTITLED = 'Поездка без названия'
const PHONE_TRIPS = 2

const title = (trip: ChatMeta) => trip.title ?? UNTITLED

/** The shortest title fits beside the plan card; the rest get the full width below. */
function arrange(trips: ChatMeta[]): { beside?: ChatMeta; below: ChatMeta[] } {
  const beside = trips.reduce<ChatMeta | undefined>(
    (shortest, trip) => (shortest && title(shortest).length <= title(trip).length ? shortest : trip),
    undefined,
  )
  return { beside, below: trips.filter((trip) => trip !== beside) }
}

interface MenuLinkProps {
  label: string
  onClick: () => void
  dark?: boolean
  center?: boolean
}

function MenuLink({ label, onClick, dark, center }: MenuLinkProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        'flex h-11 w-full min-w-0 items-center gap-2 rounded-xl px-3.5 text-left text-[14px] font-medium transition-colors',
        dark ? 'bg-white/12 text-white hover:bg-white/22' : 'bg-white/85 text-foreground shadow-sm hover:bg-white',
        center && 'justify-center',
      )}
    >
      <ArrowUpRightIcon aria-hidden className={cn('h-4 w-4 shrink-0', dark ? 'text-white/80' : 'text-highlight')} />
      <span className="min-w-0 truncate">{label}</span>
    </button>
  )
}

interface TripsMenuProps {
  hasTrips: boolean
  trips: ChatMeta[]
}

/** The landing menu: «Спланировать» in the corner, the user's latest trips wrapped around it in blue; stacked on a phone. */
export function TripsMenu({ hasTrips, trips }: TripsMenuProps) {
  const go = useContext(CardNavGoContext)
  const isMobile = useIsMobile()
  const openTrip = (trip: ChatMeta) => go(`/chat/${trip.id}`)
  const plan = (
    <div className="relative z-10 flex flex-col gap-2 rounded-2xl bg-accent p-4">
      <h3 className="m-0 flex min-h-7 items-center text-[17px] font-semibold tracking-tight text-foreground">Спланировать</h3>
      <MenuLink label="Новая поездка" onClick={() => go('/chat')} />
    </div>
  )
  if (!hasTrips) return <div data-nav-card>{plan}</div>

  if (isMobile) {
    return (
      <div className="flex flex-col gap-2">
        <div data-nav-card>{plan}</div>
        <div data-nav-card className="flex flex-col gap-2 rounded-2xl bg-highlight p-4">
          <h3 className="m-0 flex min-h-7 items-center text-[17px] font-semibold tracking-tight text-white">Мои поездки</h3>
          <MenuLink label="Все поездки" onClick={() => go('/chat')} dark />
          {trips.slice(0, PHONE_TRIPS).map((trip) => (
            <MenuLink key={trip.id} label={title(trip)} onClick={() => openTrip(trip)} dark />
          ))}
        </div>
      </div>
    )
  }

  const { beside, below } = arrange(trips)
  return (
    <div data-nav-card className="grid grid-cols-2 gap-x-2">
      <div className="relative mb-2">
        {/* the inner corner of the blue shape; 1px past each blue edge so no seam shows while it moves */}
        <span
          aria-hidden
          className="absolute -right-[9px] -bottom-[9px] size-[25px] bg-[radial-gradient(circle_at_0_0,transparent_23.5px,var(--highlight)_24px)]"
        />
        {plan}
      </div>

      <div className="-mb-4 flex min-w-0 flex-col gap-2 rounded-t-2xl bg-highlight px-4 pt-4">
        <div className="flex min-h-7 items-center justify-between gap-2">
          <h3 className="m-0 text-[17px] font-semibold tracking-tight text-white">Мои поездки</h3>
          {below.length > 0 && (
            <button
              type="button"
              onClick={() => go('/chat')}
              className="-mr-1 inline-flex shrink-0 items-center gap-1 rounded-lg px-1.5 py-1 text-[13px] font-medium text-white/75 transition-colors hover:text-white"
            >
              Все поездки
              <ArrowRightIcon aria-hidden className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        {beside && <MenuLink label={title(beside)} onClick={() => openTrip(beside)} dark />}
      </div>

      <div className="col-span-2 flex flex-col gap-2 rounded-b-2xl rounded-tl-2xl bg-highlight p-4">
        {below.length > 0 ? (
          below.map((trip) => <MenuLink key={trip.id} label={title(trip)} onClick={() => openTrip(trip)} dark />)
        ) : (
          <MenuLink label="Все поездки" onClick={() => go('/chat')} dark center />
        )}
      </div>
    </div>
  )
}
