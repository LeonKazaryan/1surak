import {
  CheckBadgeIcon,
  ExclamationTriangleIcon,
  FaceSmileIcon,
  IdentificationIcon,
  MinusIcon,
  PaperAirplaneIcon,
  PlusIcon,
} from '@heroicons/react/20/solid'
import type { DestinationCard, DestinationClimate } from '@/types/api'
import { flagEmoji, keepPricesTogether } from '../widgets'
import { Fact, PriceLevel, TicketStrip } from './DestinationCards'
import { Section } from './DetailsPanel'
import { temp, travelText } from './ticketFormat'
import { TripArt } from './TripArt'
import { VisaChip } from './VisaChip'

function Weather({ climate }: { climate: DestinationClimate }) {
  const stats = [
    ['Днём', climate.day !== undefined && temp(climate.day)],
    ['Ночью', climate.night !== undefined && temp(climate.night)],
    ['Море', climate.sea !== undefined && temp(climate.sea)],
    ['Дождливых дней', climate.rain_days !== undefined && (climate.rain_days < 1 ? 'почти нет' : String(Math.round(climate.rain_days)))],
  ].filter((stat): stat is [string, string] => Boolean(stat[1]))
  if (!stats.length) return null
  const title = `Погода в ${climate.month_in}`
  return (
    <Section title={title}>
      <ul aria-label={title} className="m-0 grid list-none grid-cols-2 gap-2 p-0">
        {stats.map(([label, value]) => (
          <li key={label} className="rounded-xl bg-inset px-3 py-2">
            <span className="block text-[12px] text-muted-foreground">{label}</span>
            <span className="block text-[17px] font-semibold text-foreground tabular-nums">{value}</span>
          </li>
        ))}
      </ul>
    </Section>
  )
}

/** Everything known about one suggested place, shown in the details panel. */
export function PlaceDetails({ card }: { card: DestinationCard }) {
  const travel = travelText(card)

  return (
    <>
      <div className="relative h-36 shrink-0 overflow-hidden rounded-2xl">
        <TripArt kind={card.kinds[0] ?? 'sea'} seed={card.id} photo={card.photo} still />
        <div className="pointer-events-none absolute inset-0 bg-linear-to-t from-slate-950/70 to-transparent" />
        <p className="absolute bottom-3 left-4 m-0 text-[13px] font-medium text-white">
          <span className="mr-1">{flagEmoji(card.country_code)}</span>
          {card.country}
        </p>
      </div>

      <p className="m-0 text-[14px] leading-relaxed text-foreground">{keepPricesTogether(card.why)}</p>

      {card.climate && <Weather climate={card.climate} />}

      <Section title="Дорога">
        {card.flight ? (
          <TicketStrip flight={card.flight} change={card.price_change} />
        ) : (
          <ul className="m-0 list-none p-0">
            <Fact icon={PaperAirplaneIcon} tone={travel ? 'default' : 'warn'}>
              {travel ?? 'билетов не нашлось'}
            </Fact>
          </ul>
        )}
      </Section>

      <Section title="Коротко">
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {card.visa_info ? (
            <VisaChip info={card.visa_info} />
          ) : (
            <Fact icon={card.visa_easy ? CheckBadgeIcon : IdentificationIcon} tone={card.visa_easy ? 'good' : 'warn'}>
              {card.visa}
            </Fact>
          )}
          {card.price_level && card.price && (
            <li>
              <PriceLevel level={card.price_level} label={card.price} />
            </li>
          )}
          {card.kids && (
            <Fact icon={FaceSmileIcon} tone={card.kids_fit === 'poor' ? 'warn' : 'default'}>
              {card.kids}
            </Fact>
          )}
        </ul>
      </Section>

      {card.highlights.length > 0 && (
        <Section title="Что понравится">
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {card.highlights.map((text) => (
              <li key={text} className="flex items-start gap-2 text-[14px] leading-snug text-foreground">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary">
                  <PlusIcon className="h-3 w-3 text-primary-foreground" aria-hidden />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {(card.watch_out.length > 0 || card.tradeoff) && (
        <Section title="Что учесть">
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {card.tradeoff && (
              <li className="flex items-start gap-2 text-[14px] leading-snug text-foreground">
                <MinusIcon className="mt-0.5 h-4 w-4 shrink-0 text-faint" aria-hidden />
                {keepPricesTogether(card.tradeoff)}
              </li>
            )}
            {card.watch_out.map((text) => (
              <li key={text} className="flex items-start gap-2 text-[14px] leading-snug text-muted-foreground">
                <ExclamationTriangleIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
                {text}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  )
}
