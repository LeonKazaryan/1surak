import { useId, useState, type ComponentType } from 'react'
import { motion } from 'motion/react'
import { BuildingOffice2Icon, CameraIcon, HomeIcon, MapIcon, MapPinIcon, SunIcon } from '@heroicons/react/20/solid'
import { ScrollRow } from '@/components/ScrollRow'
import { cn } from '@/components/ui/utils'
import type { PlanDay, PlanItem, PlanItemKind, PlanStop } from '@/types/api'
import { ModeIcon } from '../components/RouteCard'
import { TripArt } from '../components/TripArt'
import { PlanSection } from './planParts'
import { dayChip } from './planFormat'

type IconProps = { className?: string }

function FoodIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M5 2.5v5a2 2 0 0 0 4 0v-5M7 2.5v15M14.5 17.5v-15c-1.8 1-3 3.2-3 6.2 0 1.6.9 2.8 3 2.8" />
    </svg>
  )
}

function CarIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden fill="currentColor">
      <path d="M4.6 5.2A2 2 0 0 1 6.5 4h7a2 2 0 0 1 1.9 1.2l1.3 3.3A2 2 0 0 1 18 10.3V14a1 1 0 0 1-1 1h-.6a2 2 0 0 1-3.8 0H7.4a2 2 0 0 1-3.8 0H3a1 1 0 0 1-1-1v-3.7a2 2 0 0 1 1.3-1.8zM6.2 6l-1 2.5h9.6L13.8 6z" />
    </svg>
  )
}

function PlaneIcon({ className }: IconProps) {
  return <ModeIcon mode="flight" className={className} />
}

function BusIcon({ className }: IconProps) {
  return <ModeIcon mode="ground" className={className} />
}

const KIND_LOOK: Record<PlanItemKind, { Icon: ComponentType<IconProps>; tone: string }> = {
  flight: { Icon: PlaneIcon, tone: 'bg-highlight/10 text-highlight' },
  move: { Icon: BusIcon, tone: 'bg-highlight/10 text-highlight' },
  transfer: { Icon: CarIcon, tone: 'bg-highlight/10 text-highlight' },
  hotel: { Icon: BuildingOffice2Icon, tone: 'bg-highlight/10 text-highlight' },
  sight: { Icon: CameraIcon, tone: 'bg-primary/45 text-[#3f7d22]' },
  trip: { Icon: MapIcon, tone: 'bg-primary/45 text-[#3f7d22]' },
  walk: { Icon: MapPinIcon, tone: 'bg-secondary text-secondary-foreground' },
  food: { Icon: FoodIcon, tone: 'bg-amber-100 text-amber-700' },
  beach: { Icon: SunIcon, tone: 'bg-sky-100 text-sky-600' },
  free: { Icon: HomeIcon, tone: 'bg-secondary text-secondary-foreground' },
}

function ItemRow({ item, last }: { item: PlanItem; last: boolean }) {
  const { Icon, tone } = KIND_LOOK[item.kind]
  const photo = item.spot?.photo
  return (
    <li className="relative flex gap-3 pb-4 last:pb-0">
      <span className="w-11 shrink-0 pt-1.5 text-right text-[13px] font-medium text-muted-foreground tabular-nums">{item.time ?? ''}</span>
      <span className="relative flex flex-col items-center">
        <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-full', tone)}>
          <Icon className="h-4 w-4" />
        </span>
        {!last && <span aria-hidden className="w-px flex-1 bg-border" />}
      </span>
      <span className="flex min-w-0 flex-1 gap-3 pt-1">
        <span className="min-w-0 flex-1">
          <span className="block text-[14px] leading-snug font-medium text-foreground">{item.title}</span>
          {item.note && <span className="block text-[13px] leading-snug text-muted-foreground">{item.note}</span>}
          {item.spot?.hours && <span className="block text-[12px] text-faint">{item.spot.hours}</span>}
        </span>
        {photo && (
          <span className="relative h-14 w-[72px] shrink-0 overflow-hidden rounded-xl">
            <TripArt kind="city" seed={item.spot?.id} photo={photo} still className="absolute inset-0" />
          </span>
        )}
      </span>
    </li>
  )
}

function Taste({ stop }: { stop: PlanStop }) {
  if (!stop.dishes.length && !stop.food_intro) return null
  return (
    <div className="flex flex-col gap-2 rounded-2xl bg-amber-50 p-4">
      <p className="m-0 flex items-center gap-2 text-[13px] font-semibold text-foreground">
        <FoodIcon className="h-4 w-4 text-amber-700" />
        Что попробовать
      </p>
      {stop.food_intro && <p className="m-0 text-[13px] leading-snug text-muted-foreground">{stop.food_intro}</p>}
      {stop.dishes.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {stop.dishes.map((dish) => (
            <li key={dish.name} className="text-[13px] leading-snug">
              <span className="font-semibold text-foreground">{dish.name}</span>
              {dish.note && <span className="text-muted-foreground">{`: ${dish.note}`}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

interface PlanDaysProps {
  days: PlanDay[]
  stops: PlanStop[]
}

/** The trip one day at a time: pick a day on the strip, read its timeline. */
export function PlanDays({ days, stops }: PlanDaysProps) {
  const pillId = useId()
  const [picked, setPicked] = useState(0)
  const index = Math.min(picked, days.length - 1)
  const day = days[index]
  if (!day) return null
  const stop = stops.find((s) => s.place_id === day.place_id) ?? stops[0]

  return (
    <PlanSection title="По дням">
      <ScrollRow label="Дни поездки" className="-mx-4 sm:-mx-6" rowClassName="gap-1.5 px-4 sm:px-6">
        {days.map((d, i) => {
          const chip = dayChip(d.date)
          const selected = i === index
          return (
            <button
              key={d.date}
              type="button"
              aria-label={chip.label}
              aria-pressed={selected}
              onClick={() => setPicked(i)}
              className={cn(
                'relative flex h-14 w-12 shrink-0 flex-col items-center justify-center rounded-2xl border transition-colors',
                selected ? 'border-transparent text-primary-foreground' : 'border-border bg-card text-foreground hover:bg-accent/60',
              )}
            >
              {selected && (
                <motion.span layoutId={pillId} className="absolute inset-0 rounded-[15px] bg-primary" transition={{ type: 'spring', stiffness: 460, damping: 34 }} />
              )}
              <span className="relative text-[11px] leading-none font-medium uppercase opacity-70">{chip.weekday}</span>
              <span className="relative mt-1 text-[17px] leading-none font-semibold tabular-nums">{chip.day}</span>
            </button>
          )
        })}
      </ScrollRow>

      <motion.div key={day.date} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="flex flex-col gap-4">
        <div>
          <h5 className="m-0 text-[17px] leading-tight font-semibold tracking-tight text-foreground">{day.title}</h5>
          <p className="m-0 mt-0.5 text-[12px] text-muted-foreground">
            {`День ${index + 1} из ${days.length}`}
            {stops.length > 1 && ` · ${stop.name}`}
          </p>
        </div>
        {day.items.length > 0 ? (
          <ol className="m-0 list-none p-0">
            {day.items.map((item, i) => (
              <ItemRow key={`${item.time}-${item.title}`} item={item} last={i === day.items.length - 1} />
            ))}
          </ol>
        ) : (
          <p className="m-0 text-[13px] text-muted-foreground">Свободный день.</p>
        )}
        <Taste stop={stop} />
        {stop.source_url && (day.items.some((i) => i.spot) || stop.dishes.length > 0 || stop.food_intro) && (
          <p className="m-0 text-[11px] text-faint">
            Фото: Wikimedia Commons · тексты:{' '}
            <a href={stop.source_url} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
              Викигид
            </a>
            , CC BY-SA
          </p>
        )}
      </motion.div>
    </PlanSection>
  )
}
