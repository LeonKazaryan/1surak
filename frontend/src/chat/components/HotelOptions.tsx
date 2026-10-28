import { useContext } from 'react'
import { DataCredit } from '@/components/DataCredit'
import { fromOsm } from '@/lib/dataSources'
import { motion } from 'motion/react'
import { MapPinIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import type { HotelOption, HotelOptionsEvent } from '@/types/api'
import { HotelGallery } from '../plan/HotelGallery'
import { HotelPhoto, PriceSource, SourceBadge } from '../plan/PlanStay'
import { Stars } from '../plan/planParts'
import { dayText, nightsText } from '../plan/planFormat'
import { WishChips } from '../plan/WishProof'
import { CurrencyContext, RUB, formatMoney, plural } from '../widgets'

function Option({ hotel, index, canPick, onPick }: { hotel: HotelOption; index: number; canPick: boolean; onPick: () => void }) {
  const currency = useContext(CurrencyContext)
  return (
    <motion.li
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 26, delay: index * 0.05 }}
      className={cn(
        'flex list-none flex-col gap-2 overflow-hidden rounded-2xl border bg-card p-4',
        hotel.current ? 'border-primary' : 'border-border',
      )}
    >
      {hotel.photos?.length ? (
        <HotelGallery photos={hotel.photos} roomPhotos={hotel.room?.photos} name={hotel.name} className="-mx-4 -mt-4 h-44" />
      ) : (
        hotel.photo && <HotelPhoto photo={hotel.photo} name={hotel.name} />
      )}
      <div className="flex items-start gap-2">
        <h4 className="m-0 min-w-0 flex-1 text-[15px] leading-snug font-semibold text-foreground">{hotel.name}</h4>
        <SourceBadge hotel={hotel} />
        {hotel.rating != null && (
          <span
            title={hotel.reviews ? `${hotel.reviews.toLocaleString('ru-RU')} ${plural(hotel.reviews, ['отзыв', 'отзыва', 'отзывов'])}` : undefined}
            className="shrink-0 rounded-lg bg-highlight px-1.5 py-0.5 text-[12px] font-semibold text-white tabular-nums"
          >
            {hotel.rating.toLocaleString('ru-RU', { minimumFractionDigits: 1 })}
          </span>
        )}
      </div>
      <p className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted-foreground">
        {hotel.stars_known && <Stars count={hotel.stars} />}
        <span className="inline-flex items-center gap-1">
          <MapPinIcon aria-hidden className="h-3.5 w-3.5 text-faint" />
          {hotel.area}
        </span>
        {(hotel.maps_url ?? hotel.source_url) && (
          <a href={hotel.maps_url ?? hotel.source_url ?? undefined} target="_blank" rel="noopener noreferrer" className="text-highlight underline-offset-2 hover:underline">
            на карте
          </a>
        )}
      </p>
      {hotel.room?.name && (
        <p className="m-0 text-[12px] leading-snug text-muted-foreground">
          <span className="font-medium text-foreground">{hotel.room.name}</span>
          {[hotel.room.size_m2 && `${hotel.room.size_m2} м²`, hotel.room.view].filter(Boolean).map((fact) => ` · ${fact}`)}
        </p>
      )}
      <WishChips evidence={hotel.evidence} />
      <div className="mt-auto flex items-end gap-3 pt-1">
        <span className="min-w-0 flex-1">
          <span className="block text-lg font-semibold text-foreground tabular-nums">
            {hotel.price_estimate && hotel.real ? 'около ' : ''}
            {formatMoney(hotel.total_rub, currency)}
          </span>
          <span className="block text-[12px] text-muted-foreground">
            {formatMoney(hotel.night_rub, currency)} за ночь{hotel.terms_known ? ` · ${hotel.meal_label}` : ''}
          </span>
          {hotel.cancel_until && <span className="block text-[12px] font-medium text-[#3f7d22]">{`Бесплатная отмена до ${dayText(hotel.cancel_until)}`}</span>}
        </span>
        {hotel.current ? (
          <span className="shrink-0 rounded-full bg-primary px-3 py-1.5 text-[12px] font-semibold text-primary-foreground">В плане</span>
        ) : (
          <button
            type="button"
            onClick={onPick}
            disabled={!canPick}
            aria-label={`Выбрать «${hotel.name}»`}
            className="h-9 shrink-0 rounded-full bg-primary px-4 text-[13px] font-semibold text-primary-foreground transition-colors hover:bg-primary-hover disabled:bg-secondary disabled:text-faint"
          >
            Выбрать
          </button>
        )}
      </div>
    </motion.li>
  )
}

/** More hotels for one place of the trip: picking one rebuilds the plan with it. */
export function HotelOptionsCards({ widget, canPick, onPick }: { widget: HotelOptionsEvent; canPick: boolean; onPick: (name: string) => void }) {
  return (
    <CurrencyContext.Provider value={widget.currency ?? RUB}>
      <p className="m-0 mt-3 text-[12px] text-muted-foreground">
        {`${widget.place}: ${nightsText(widget.nights)}, цена за всё проживание`}
      </p>
      <ul className="m-0 mt-2 grid gap-3 p-0 sm:grid-cols-2">
        {widget.hotels.map((hotel, i) => (
          <Option key={hotel.id} hotel={hotel} index={i} canPick={canPick} onPick={() => onPick(hotel.name)} />
        ))}
      </ul>
      {widget.hotels.some((hotel) => fromOsm(hotel.source_url)) && <DataCredit sources={['osm']} className="mt-2" />}
      {widget.hotels[0] && <PriceSource hotel={widget.hotels[0]} className="mt-2" />}
    </CurrencyContext.Provider>
  )
}
