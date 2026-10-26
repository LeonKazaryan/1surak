import { useContext } from 'react'
import { CheckIcon, MinusIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { Photo, PlanHotel, PlanStop } from '@/types/api'
import { CurrencyContext, formatMoney, plural } from '../widgets'
import { PlanSection, Stars } from './planParts'
import { nightsText, spanText } from './planFormat'
import { WishProof } from './WishProof'

function cancelText(hotel: PlanHotel): string {
  if (hotel.free_cancel_days === null) return 'без бесплатной отмены'
  const days = hotel.free_cancel_days
  return `бесплатная отмена за ${days} ${plural(days, ['день', 'дня', 'дней'])} до заезда`
}

function Rating({ hotel }: { hotel: PlanHotel }) {
  if (hotel.rating === null || hotel.reviews === null) return null
  return (
    <span className="flex shrink-0 items-center gap-1.5">
      <span className="rounded-lg bg-highlight px-1.5 py-0.5 text-[13px] font-semibold text-white tabular-nums">
        {hotel.rating.toLocaleString('ru-RU', { minimumFractionDigits: 1 })}
      </span>
      <span className="text-[11px] leading-tight text-muted-foreground">
        {hotel.reviews.toLocaleString('ru-RU')}
        <br />
        {plural(hotel.reviews, ['отзыв', 'отзыва', 'отзывов'])}
      </span>
    </span>
  )
}

function Pros({ hotel }: { hotel: PlanHotel }) {
  // «в центре» already stands under the name as the area: said once
  const reasons = hotel.reasons.filter((text) => text !== hotel.area)
  if (!reasons.length && !hotel.misses.length) return null
  return (
    <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label="Почему этот отель">
      {reasons.map((text) => (
        <li key={text} className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-[12px] font-medium text-foreground">
          <CheckIcon aria-hidden className="h-3.5 w-3.5 text-[#4c9a2a]" />
          {text}
        </li>
      ))}
      {hotel.misses.map((text) => (
        <li key={text} className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-[12px] font-medium text-secondary-foreground">
          <MinusIcon aria-hidden className="h-3.5 w-3.5 text-faint" />
          {text}
        </li>
      ))}
    </ul>
  )
}

/** A real hotel's photo from Wikimedia Commons, credited as its licence asks. */
export function HotelPhoto({ photo, name }: { photo: Photo; name: string }) {
  return (
    <figure className="-mx-4 -mt-4 mb-0">
      <img src={photo.url} alt={name} loading="lazy" className="block h-40 w-full object-cover" />
      <figcaption className="px-4 pt-1 text-[11px] text-faint">
        Фото:{' '}
        <a href={photo.file_url} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
          {photo.author}, {photo.license}
        </a>
      </figcaption>
    </figure>
  )
}

/** Demo: invented whole. Real: the hotel exists, the price is our estimate until booking. */
export function SourceBadge({ hotel }: { hotel: { real?: boolean } }) {
  const [label, title] = hotel.real
    ? ['цена ориентировочная', 'Настоящий отель; цену и условия уточним при бронировании']
    : ['демо', 'Демонстрационный отель: цены и номера сгенерированы']
  return (
    <span className="shrink-0 rounded-full bg-secondary px-2 py-0.5 text-[11px] font-medium whitespace-nowrap text-muted-foreground" title={title}>
      {label}
    </span>
  )
}

function HotelCard({ hotel, transferText }: { hotel: PlanHotel; transferText: string | null }) {
  const currency = useContext(CurrencyContext)
  const where = [hotel.area, hotel.beach_m !== null && `до пляжа ${hotel.beach_m} м`].filter(Boolean).join(' · ')
  const unknownTerms = hotel.terms_known === false
  // check-in times live in «Дорога» next to the flights, unknown terms in the badge's title: said once
  const facts = [
    ...(unknownTerms ? [] : [hotel.meal_label, cancelText(hotel), hotel.pay_at_hotel ? 'оплата в отеле' : 'оплата при бронировании']),
    hotel.rooms > 1 && `${hotel.rooms} ${plural(hotel.rooms, ['номер', 'номера', 'номеров'])}`,
    transferText,
  ].filter((fact): fact is string => Boolean(fact))
  return (
    <div className="flex flex-col gap-3 overflow-hidden rounded-2xl border border-border p-4">
      {hotel.photo && <HotelPhoto photo={hotel.photo} name={hotel.name} />}
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h5 className="m-0 min-w-0 text-[17px] leading-tight font-semibold tracking-tight text-foreground">{hotel.name}</h5>
            <SourceBadge hotel={hotel} />
          </div>
          <div className="mt-1 flex min-w-0 items-start gap-2 text-[13px] leading-snug text-muted-foreground">
            {hotel.stars_known !== false && (
              <span className="flex h-[18px] shrink-0 items-center">
                <Stars count={hotel.stars} />
              </span>
            )}
            <span className="min-w-0">{where}</span>
          </div>
        </div>
        <Rating hotel={hotel} />
      </div>
      <Pros hotel={hotel} />
      <WishProof evidence={hotel.evidence} />
      {facts.length > 0 && (
      <ul className="m-0 grid list-none grid-cols-1 gap-x-4 gap-y-1 p-0 text-[13px] text-foreground sm:grid-cols-2">
        {facts.map((fact) => (
          <li key={fact} className="flex items-start gap-2 leading-snug">
            <span aria-hidden className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-faintest" />
            {fact[0].toUpperCase() + fact.slice(1)}
          </li>
        ))}
      </ul>
      )}
      <div className="flex items-baseline justify-between gap-3 border-t border-border pt-3">
        <span className="text-[12px] text-muted-foreground">
          {nightsText(hotel.nights)} · {hotel.price_estimate && hotel.real ? 'около ' : ''}
          {formatMoney(hotel.night_rub, currency)} за ночь
          {hotel.source_url && (
            <a href={hotel.source_url} target="_blank" rel="noopener noreferrer" className="ml-2 text-highlight underline-offset-2 hover:underline">
              на карте
            </a>
          )}
        </span>
        <span className="shrink-0 text-lg font-semibold whitespace-nowrap text-foreground tabular-nums">{formatMoney(hotel.total_rub, currency)}</span>
      </div>
    </div>
  )
}

interface AlternativeProps {
  hotel: PlanHotel
  best: PlanHotel
  canAct: boolean
  onPick: () => void
}

function Alternative({ hotel, best, canAct, onPick }: AlternativeProps) {
  const currency = useContext(CurrencyContext)
  const gap = hotel.total_rub - best.total_rub
  return (
    <li className="flex items-center gap-3 rounded-2xl bg-inset px-3.5 py-3">
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-1.5">
          <span className="text-[14px] font-semibold text-foreground">{hotel.name}</span>
          {hotel.stars_known !== false && <Stars count={hotel.stars} />}
        </span>
        <span className="block text-[12px] leading-snug text-muted-foreground">
          {[
            ...(hotel.evidence ?? []).filter((e) => e.verdict === 'yes').map((e) => e.wish),
            hotel.terms_known === false ? null : hotel.meal_label,
            ...hotel.reasons.slice(0, 2),
          ]
            .filter(Boolean)
            .slice(0, 3)
            .join(' · ')}
        </span>
        <span className={cn('block text-[12px] font-medium tabular-nums', gap < 0 ? 'text-[#3f7d22]' : 'text-muted-foreground')}>
          {formatMoney(hotel.total_rub, currency)}
          {gap !== 0 && `, ${gap < 0 ? 'дешевле' : 'дороже'} на ${formatMoney(Math.abs(gap), currency)}`}
        </span>
      </span>
      <button
        type="button"
        onClick={onPick}
        disabled={!canAct}
        aria-label={`Выбрать «${hotel.name}»`}
        className="h-9 shrink-0 rounded-full border border-border bg-card px-4 text-[13px] font-semibold text-foreground transition-colors hover:border-highlight/30 hover:bg-accent disabled:opacity-50"
      >
        Выбрать
      </button>
    </li>
  )
}

function transferText(stop: PlanStop, currency: Parameters<typeof formatMoney>[1]): string | null {
  const ride = stop.transfer_in
  if (!ride) return null
  const way = ride.mode === 'boat' ? 'катер' : 'такси'
  // a price from the city's own airport fare says where it comes from; one by the kilometre is an estimate
  const basis = ride.source ? `по тарифу ${ride.source}` : ride.mode === 'boat' ? 'оценка' : 'оценка по расстоянию'
  return `трансфер из аэропорта: ${way}, около ${ride.minutes} мин, ${formatMoney(ride.price_rub, currency)} (${basis})`
}

interface PlanStayProps {
  stops: PlanStop[]
  canAct: boolean
  onAsk: (text: string) => void
}

/** The hotel picked for each stop with its reasons and misses, the other options and what was ruled out. */
export function PlanStay({ stops, canAct, onAsk }: PlanStayProps) {
  const currency = useContext(CurrencyContext)
  return (
    <PlanSection title="Где живёте">
      {stops.map((stop) => (
        <div key={stop.place_id} className="flex flex-col gap-3">
          {stops.length > 1 && (
            <p className="m-0 text-[13px] font-semibold text-foreground">
              {stop.name} <span className="font-normal text-muted-foreground">· {spanText(stop.check_in, stop.check_out)}</span>
            </p>
          )}
          <HotelCard hotel={stop.hotel} transferText={transferText(stop, currency)} />
          {stop.alternatives.length > 0 && (
            <ul aria-label="Другие варианты" className="m-0 flex list-none flex-col gap-2 p-0">
              {stop.alternatives.map((hotel) => (
                <Alternative
                  key={hotel.id}
                  hotel={hotel}
                  best={stop.hotel}
                  canAct={canAct}
                  onPick={() => onAsk(`Хочу отель «${hotel.name}» вместо «${stop.hotel.name}»`)}
                />
              ))}
            </ul>
          )}
          <button
            type="button"
            onClick={() => onAsk(`Покажи ещё отели: ${stop.name}`)}
            disabled={!canAct}
            className="self-start rounded-full px-1 text-[13px] font-medium text-highlight underline-offset-4 hover:underline disabled:opacity-50"
          >
            Ещё отели
          </button>
          {stop.excluded.length > 0 && (
            <ul aria-label="Не предлагаю" className="m-0 flex list-none flex-col gap-1 p-0 text-[12px] leading-snug text-muted-foreground">
              {stop.excluded.map((hotel) => (
                <li key={hotel.name} className="flex items-start gap-1.5">
                  <MinusIcon aria-hidden className="mt-px h-3.5 w-3.5 shrink-0 text-faint" />
                  {`Не предлагаю «${hotel.name}», ${hotel.stars} ${plural(hotel.stars, ['звезда', 'звезды', 'звёзд'])}: ${hotel.reason}`}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </PlanSection>
  )
}
