import { Fragment } from 'react'
import { CheckBadgeIcon, FaceSmileIcon, IdentificationIcon, MinusIcon } from '@heroicons/react/20/solid'
import type { RouteCard, RouteStop } from '@/types/api'
import { flagEmoji, keepPricesTogether, plural } from '../widgets'
import { Fact } from './DestinationCards'
import { Section } from './DetailsPanel'
import { LegRow, RouteTotal } from './RouteCard'
import { sceneKinds } from './routeScenes'
import { temp } from './ticketFormat'
import { TripArt } from './TripArt'

function Banner({ card }: { card: RouteCard }) {
  const scenes = sceneKinds(card.stops)
  return (
    <div className="flex h-32 shrink-0 overflow-hidden rounded-2xl">
      {card.stops.map((stop, i) => (
        <div key={stop.id} className="relative min-w-0 flex-1">
          <TripArt kind={scenes[i]} seed={stop.id} photo={stop.photo} still className="absolute inset-0" />
          <span className="pointer-events-none absolute inset-0 bg-linear-to-t from-slate-950/60 to-transparent" />
          <p className="absolute right-3 bottom-2.5 left-3 m-0 truncate text-[13px] font-semibold text-white">{stop.name}</p>
        </div>
      ))}
    </div>
  )
}

function StopRow({ stop, index }: { stop: RouteStop; index: number }) {
  return (
    <li className="flex gap-3 rounded-2xl bg-inset px-2 py-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-highlight text-[13px] font-semibold text-white">
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        <p className="m-0 flex items-baseline justify-between gap-2">
          <span className="min-w-0 truncate text-[15px] font-semibold text-foreground">{stop.name}</span>
          <span className="shrink-0 text-[12px] text-muted-foreground tabular-nums">
            {stop.nights} {plural(stop.nights, ['ночь', 'ночи', 'ночей'])}
            {stop.day !== null && ` · ${temp(stop.day)}`}
          </span>
        </p>
        <p className="m-0 text-[12px] text-muted-foreground">
          <span className="mr-1">{flagEmoji(stop.country_code)}</span>
          {stop.country}
        </p>
        {stop.highlights.length > 0 && (
          <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0">
            {stop.highlights.map((text) => (
              <li key={text} className="flex items-start gap-2 text-[13px] leading-snug text-foreground">
                <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#4c9a2a]" />
                {text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  )
}

/** The whole route day by day: each flight or drive, then the city it brings you to. */
export function RouteDetails({ card }: { card: RouteCard }) {
  const countries = [...new Map(card.stops.map((s) => [s.country, s])).values()]
  return (
    <>
      <Banner card={card} />

      <p className="m-0 text-[14px] leading-relaxed text-foreground">{keepPricesTogether(card.why)}</p>

      <Section title="Маршрут">
        <ol aria-label="Маршрут" className="m-0 flex list-none flex-col gap-1 p-0">
          {card.legs.map((leg, i) => (
            <Fragment key={`${i}-${leg.from}-${leg.to}`}>
              <LegRow leg={leg} index={i} />
              {card.stops[i] && <StopRow stop={card.stops[i]} index={i} />}
            </Fragment>
          ))}
        </ol>
      </Section>

      <Section title="Билеты">
        <RouteTotal card={card} />
      </Section>

      <Section title="Коротко">
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {countries.map((s) => (
            <Fact key={s.country} icon={s.visa_easy ? CheckBadgeIcon : IdentificationIcon} tone={s.visa_easy ? 'good' : 'warn'}>
              {`${s.country}: ${s.visa}`}
            </Fact>
          ))}
          <Fact icon={FaceSmileIcon}>{card.kids}</Fact>
        </ul>
      </Section>

      {card.tradeoff && (
        <Section title="Что учесть">
          <p className="m-0 flex items-start gap-2 text-[14px] leading-snug text-foreground">
            <MinusIcon className="mt-0.5 h-4 w-4 shrink-0 text-faint" aria-hidden />
            {keepPricesTogether(card.tradeoff)}
          </p>
        </Section>
      )}
    </>
  )
}
