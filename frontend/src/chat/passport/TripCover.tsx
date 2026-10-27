import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { cn } from '@/components/ui/utils'
import type { Photo, TripPassport } from '@/types/api'
import { BrandBackdrop } from '../map/BrandBackdrop'
import { flagEmoji } from '../widgets'
import { PassportChips } from './PassportChips'
import { STAGES, type PassportField, type TripStage } from './passport'

const SPRING = { type: 'spring', stiffness: 260, damping: 28 } as const

/** The destination's photo over the brand's backdrop: it fades in once it has really loaded (a cached one
 * may be complete before React listens), so the title never sits white on an empty cover. */
function PhotoBackdrop({ photo, loaded, onLoaded }: { photo: Photo; loaded: boolean; onLoaded: () => void }) {
  return (
    <motion.div
      aria-hidden
      className="absolute inset-0 overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: loaded ? 1 : 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
    >
      <img
        ref={(el) => {
          if (el?.complete && el.naturalWidth > 0) onLoaded()
        }}
        src={photo.url}
        alt=""
        draggable={false}
        onLoad={onLoaded}
        className="cover-drift absolute inset-0 h-full w-full object-cover"
      />
      <span className="absolute inset-0 bg-linear-to-t from-slate-950/80 via-slate-950/30 to-slate-950/5" />
    </motion.div>
  )
}

/** Idea → options → plan → booking: how far the trip has come, the current step breathing while the agent
 * works on it. */
export function StageMeter({ stage, busy, tone }: { stage: TripStage; busy: boolean; tone: 'light' | 'dark' }) {
  const at = STAGES.findIndex((s) => s.stage === stage)
  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-semibold backdrop-blur-md',
        tone === 'dark' ? 'bg-white/85 text-foreground shadow-sm' : 'bg-white/70 text-foreground ring-1 ring-border',
      )}
      aria-label={`Этап: ${STAGES[at].label}`}
    >
      <span className="flex items-center gap-1" aria-hidden>
        {STAGES.map((s, i) => (
          <motion.span
            key={s.stage}
            layout
            transition={SPRING}
            className={cn(
              'block h-1.5 rounded-full',
              i < at ? 'w-3 bg-primary-hover' : i === at ? 'w-5 bg-primary-hover' : 'w-1.5 bg-foreground/15',
              i === at && busy && 'animate-pulse',
            )}
          />
        ))}
      </span>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={busy ? 'busy' : stage}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.2 }}
        >
          {busy ? 'Работаю…' : STAGES[at].label}
        </motion.span>
      </AnimatePresence>
    </div>
  )
}

interface TripCoverProps {
  passport: TripPassport | null | undefined
  photo: Photo | null
  stage: TripStage
  busy: boolean
  onEdit: (field: PassportField) => void
}

/** The top of a trip: the destination's photo (or the brand's colours and the map), its name and the trip
 * as chips that fill in while the agent understands the request. */
export function TripCover({ passport, photo, stage, busy, onEdit }: TripCoverProps) {
  const place = passport?.destination
  const [loaded, setLoaded] = useState<string | null>(null)
  const dark = Boolean(photo) && loaded === photo?.url
  const title = place?.name ?? (passport?.kinds.length ? passport.kinds.map((k) => k.label).join(', ') : 'Новая поездка')
  const from = passport?.origin ? { lat: passport.origin.lat, lon: passport.origin.lon } : null
  const to = place?.lat != null && place.lon != null ? { lat: place.lat, lon: place.lon } : null

  return (
    <motion.section
      initial={{ opacity: 0, y: 14, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={SPRING}
      aria-label="Поездка"
      className="relative isolate flex min-h-[208px] flex-col justify-end overflow-hidden rounded-[28px] border border-border shadow-[0_24px_60px_-42px_rgba(15,23,42,0.55)] sm:min-h-[228px]"
    >
      <BrandBackdrop from={from} to={to} />
      <AnimatePresence initial={false}>
        {photo && (
          <PhotoBackdrop key={photo.url} photo={photo} loaded={loaded === photo.url} onLoaded={() => setLoaded(photo.url)} />
        )}
      </AnimatePresence>

      <div className="absolute top-3.5 right-3.5 left-4 z-10 flex items-center justify-between gap-2">
        <span className={cn('text-[11px] font-semibold tracking-[0.14em] uppercase', dark ? 'text-white/75' : 'text-faint')}>
          Поездка
        </span>
        <StageMeter stage={stage} busy={busy} tone={dark ? 'dark' : 'light'} />
      </div>

      <div className={cn('relative z-10 flex flex-col gap-3 px-4 pt-14 pb-4 sm:px-5 sm:pb-5', dark && 'pb-6 sm:pb-6')}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.h2
            key={title}
            initial={{ opacity: 0, y: 10, filter: 'blur(6px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: -8, filter: 'blur(6px)' }}
            transition={{ duration: 0.45, ease: [0.215, 0.61, 0.355, 1] }}
            className={cn(
              'm-0 flex items-center gap-2.5 text-[26px] leading-tight font-semibold tracking-tight sm:text-[30px]',
              dark ? 'text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.35)]' : 'text-foreground',
            )}
          >
            {place?.country_code && <span className="text-[0.9em]">{flagEmoji(place.country_code)}</span>}
            <span className="min-w-0 truncate first-letter:uppercase">{title}</span>
          </motion.h2>
        </AnimatePresence>
        <PassportChips passport={passport} variant={dark ? 'cover' : 'cover-light'} onEdit={onEdit} />
      </div>
      {photo && dark && (
        <span className="absolute right-3 bottom-1.5 z-10 max-w-[45%] truncate text-[10px] text-white/55" title={`Фото: ${photo.author}, ${photo.license}`}>
          Фото: {photo.author}, {photo.license}
        </span>
      )}
    </motion.section>
  )
}

/** The trip in the header once the cover has scrolled away: the flag, the place and when. */
export function CompactPassport({ passport, onClick }: { passport: TripPassport | null | undefined; onClick: () => void }) {
  const place = passport?.destination
  return (
    <motion.button
      type="button"
      onClick={onClick}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={SPRING}
      title="К началу поездки"
      className="flex max-w-[min(60vw,34rem)] min-w-0 items-center gap-2 rounded-full border border-border bg-card/90 py-1 pr-1.5 pl-3 text-[13px] font-semibold text-foreground shadow-sm backdrop-blur-md transition-colors hover:border-faintest"
    >
      {place?.country_code && <span>{flagEmoji(place.country_code)}</span>}
      <span className="truncate">{place?.name ?? 'Поездка'}</span>
      <PassportChips passport={passport} variant="compact" ghosts={false} max={2} className="hidden flex-nowrap sm:flex" />
    </motion.button>
  )
}
