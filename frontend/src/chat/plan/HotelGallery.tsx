import { useCallback, useEffect, useRef, useState } from 'react'
import { Dialog } from 'radix-ui'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronLeftIcon, ChevronRightIcon, XMarkIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'

const SWIPE_PX = 60

interface HotelGalleryProps {
  photos: string[]
  /** How many of the first photos are of the booked room. */
  roomPhotos?: number
  name: string
  className?: string
}

function Arrow({ side, onClick, label, className }: { side: 'left' | 'right'; onClick: () => void; label: string; className?: string }) {
  const Icon = side === 'left' ? ChevronLeftIcon : ChevronRightIcon
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(
        'absolute top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-foreground shadow-md backdrop-blur transition-[opacity,transform] hover:scale-105',
        side === 'left' ? 'left-3' : 'right-3',
        className,
      )}
    >
      <Icon aria-hidden className="h-5 w-5" />
    </button>
  )
}

/** The hotel's photos to swipe through, the booked room's first; a tap opens them full screen. */
export function HotelGallery({ photos, roomPhotos = 0, name, className }: HotelGalleryProps) {
  const [broken, setBroken] = useState<ReadonlySet<string>>(new Set())
  const [at, setAt] = useState(0)
  const [open, setOpen] = useState<number | null>(null)
  const track = useRef<HTMLDivElement>(null)
  const room = new Set(photos.slice(0, roomPhotos))
  const shown = photos.filter((url) => !broken.has(url))

  const onScroll = () => {
    const el = track.current
    if (el?.clientWidth) setAt(Math.round(el.scrollLeft / el.clientWidth))
  }
  const go = (step: number) => {
    const el = track.current
    el?.scrollTo({ left: Math.max(0, Math.min(shown.length - 1, at + step)) * el.clientWidth, behavior: 'smooth' })
  }
  if (!shown.length) return null
  const current = Math.min(at, shown.length - 1)
  return (
    <div className={cn('group relative overflow-hidden bg-secondary', className)}>
      <div ref={track} onScroll={onScroll} className="scroll-row flex h-full snap-x snap-mandatory overflow-x-auto overscroll-x-contain">
        {shown.map((url, i) => (
          <button
            key={url}
            type="button"
            onClick={() => setOpen(i)}
            aria-label={`Фото ${i + 1} из ${shown.length}${room.has(url) ? ', ваш номер' : ''}: открыть`}
            className="relative h-full w-full shrink-0 snap-center cursor-zoom-in"
          >
            <img
              src={url}
              alt=""
              loading={i === 0 ? 'eager' : 'lazy'}
              decoding="async"
              draggable={false}
              onError={() => setBroken((prev) => new Set(prev).add(url))}
              className="h-full w-full object-cover"
            />
          </button>
        ))}
      </div>
      <span aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-linear-to-t from-slate-950/45 to-transparent" />
      <span className="pointer-events-none absolute top-3 left-3 rounded-full bg-white/92 px-2.5 py-1 text-[11px] font-semibold text-foreground shadow-sm">
        {room.has(shown[current]) ? 'Ваш номер' : 'Отель'}
      </span>
      {shown.length > 1 && (
        <>
          <span className="pointer-events-none absolute right-3 bottom-3 rounded-full bg-slate-950/55 px-2 py-0.5 text-[11px] font-medium text-white tabular-nums backdrop-blur">
            {current + 1} / {shown.length}
          </span>
          {current > 0 && <Arrow side="left" onClick={() => go(-1)} label="Предыдущее фото" className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100" />}
          {current < shown.length - 1 && (
            <Arrow side="right" onClick={() => go(1)} label="Следующее фото" className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100" />
          )}
        </>
      )}
      <Lightbox photos={shown} room={room} name={name} at={open} onAt={setOpen} />
    </div>
  )
}

interface LightboxProps {
  photos: string[]
  room: ReadonlySet<string>
  name: string
  at: number | null
  onAt: (at: number | null) => void
}

function Lightbox({ photos, room, name, at, onAt }: LightboxProps) {
  const thumbs = useRef<HTMLDivElement>(null)
  const step = useCallback((by: number) => at !== null && onAt((at + by + photos.length) % photos.length), [at, onAt, photos.length])

  useEffect(() => {
    if (at === null) return
    // the neighbours load while this one is looked at
    for (const i of [at + 1, at - 1]) new Image().src = photos[(i + photos.length) % photos.length]
    thumbs.current?.querySelector<HTMLElement>(`[data-at="${at}"]`)?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
  }, [at, photos])

  return (
    <Dialog.Root open={at !== null} onOpenChange={(isOpen) => !isOpen && onAt(null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          aria-describedby={undefined}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') step(1)
            if (e.key === 'ArrowLeft') step(-1)
          }}
          className="fixed inset-0 z-50 flex flex-col outline-none"
        >
          <div className="flex items-center gap-3 px-4 pt-4 text-white">
            <Dialog.Title className="m-0 min-w-0 flex-1 truncate text-[15px] font-semibold">{name}</Dialog.Title>
            {at !== null && (
              <span className="text-[13px] text-white/70 tabular-nums">
                {room.has(photos[at]) ? 'Ваш номер · ' : ''}
                {at + 1} / {photos.length}
              </span>
            )}
            <Dialog.Close aria-label="Закрыть" className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 transition-colors hover:bg-white/20">
              <XMarkIcon aria-hidden className="h-5 w-5" />
            </Dialog.Close>
          </div>
          <div className="relative flex min-h-0 flex-1 items-center justify-center px-4 py-3">
            <AnimatePresence mode="popLayout" initial={false}>
              {at !== null && (
                <motion.img
                  key={photos[at]}
                  src={photos[at]}
                  alt={`${name}, фото ${at + 1}`}
                  draggable={false}
                  drag="x"
                  dragConstraints={{ left: 0, right: 0 }}
                  dragElastic={0.4}
                  onDragEnd={(_, info) => Math.abs(info.offset.x) > SWIPE_PX && step(info.offset.x < 0 ? 1 : -1)}
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="max-h-full max-w-full cursor-grab rounded-xl object-contain select-none active:cursor-grabbing"
                />
              )}
            </AnimatePresence>
            {photos.length > 1 && (
              <>
                <Arrow side="left" onClick={() => step(-1)} label="Предыдущее фото" className="hidden sm:flex" />
                <Arrow side="right" onClick={() => step(1)} label="Следующее фото" className="hidden sm:flex" />
              </>
            )}
          </div>
          {photos.length > 1 && (
            <div ref={thumbs} className="scroll-row flex gap-2 overflow-x-auto px-4 pb-4">
              {photos.map((url, i) => (
                <button
                  key={url}
                  type="button"
                  data-at={i}
                  onClick={() => onAt(i)}
                  aria-label={`Фото ${i + 1}`}
                  aria-current={i === at}
                  className={cn(
                    'h-12 w-16 shrink-0 overflow-hidden rounded-lg ring-2 transition-[opacity,box-shadow]',
                    i === at ? 'opacity-100 ring-white' : 'opacity-55 ring-transparent hover:opacity-90',
                  )}
                >
                  <img src={url} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
