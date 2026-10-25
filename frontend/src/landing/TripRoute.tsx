import { useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { ArrowRightIcon, CheckIcon, MinusIcon, PlusIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'
import { buildRoute, cameraAt, dockedAt, flightLayout, travel } from './route'

gsap.registerPlugin(ScrollTrigger)

const FLIGHT_QUERY = '(prefers-reduced-motion: no-preference)'
const PARALLAX = 0.55
const PARTS = ['Перелёт', 'Отель', 'Трансфер']
const TRADE_OFFS = [
  { text: 'Тёплое море', good: true },
  { text: 'В бюджете', good: true },
  { text: 'Ночной вылет', good: false },
]

interface Stop {
  title: string
  visual: ReactNode
}

const STOPS: Stop[] = [
  {
    title: 'Пишете как есть',
    visual: (
      <p className="rounded-2xl rounded-br-md bg-accent px-4 py-3 text-[15px] text-foreground">
        Хочу к морю в ноябре, до 100 тысяч
      </p>
    ),
  },
  {
    title: 'Агент собирает поездку',
    visual: (
      <ul className="flex flex-wrap gap-2">
        {PARTS.map((part) => (
          <li
            key={part}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-sm font-medium text-foreground"
          >
            <CheckIcon aria-hidden className="h-4 w-4 text-highlight" />
            {part}
          </li>
        ))}
      </ul>
    ),
  },
  {
    title: 'Объясняет выбор',
    visual: (
      <ul className="flex flex-col gap-2 text-[15px]">
        {TRADE_OFFS.map(({ text, good }) => (
          <li key={text} className={cn('flex items-center gap-2', good ? 'text-foreground' : 'text-muted-foreground')}>
            <span
              aria-hidden
              className={cn(
                'flex h-5 w-5 items-center justify-center rounded-full',
                good ? 'bg-primary text-primary-foreground' : 'bg-secondary',
              )}
            >
              {good ? <PlusIcon className="h-3.5 w-3.5" /> : <MinusIcon className="h-3.5 w-3.5" />}
            </span>
            <span className="sr-only">{good ? 'Плюс:' : 'Минус:'}</span>
            {text}
          </li>
        ))}
      </ul>
    ),
  },
]

function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    () => matchMedia(query).matches,
  )
}

function SectionLabel({ className }: { className?: string }) {
  return (
    <h2
      className={cn(
        'inline-block rounded-full bg-accent px-3 py-1 text-xs font-semibold uppercase tracking-wider text-foreground',
        className,
      )}
    >
      Как это работает
    </h2>
  )
}

interface StopCardProps {
  index: number
  stop: Stop
  className?: string
}

function StopCard({ index, stop, className }: StopCardProps) {
  return (
    <article
      data-stop={index}
      className={cn(
        'w-[22rem] rounded-3xl border border-border bg-card p-6 shadow-[0_24px_64px_-28px_rgba(15,23,42,0.35)]',
        className,
      )}
    >
      <span className="text-sm font-semibold text-highlight tabular-nums">0{index + 1}</span>
      <h3 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">{stop.title}</h3>
      <div className="mt-4">{stop.visual}</div>
    </article>
  )
}

function Arrival({ className }: { className?: string }) {
  return (
    <div data-stop={STOPS.length} className={cn('flex flex-col items-center text-center', className)}>
      <div className="relative">
        <span aria-hidden className="absolute inset-x-2 bottom-0 h-10 rounded-[50%] bg-primary/50 blur-xl" />
        <img src="/mascot.png" alt="" draggable={false} className="relative h-44 w-44 object-contain" />
      </div>
      <h3 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">Поездка готова</h3>
      <Link
        to="/chat"
        viewTransition
        className="mt-5 inline-flex h-11 items-center gap-2 rounded-full bg-primary px-6 text-[15px] font-semibold text-primary-foreground transition-colors hover:bg-primary-hover"
      >
        Спланировать поездку
        <ArrowRightIcon aria-hidden className="h-4 w-4" />
      </Link>
    </div>
  )
}

function Plane() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="h-10 w-10 text-highlight drop-shadow-[0_8px_12px_rgba(10,64,209,0.35)]">
      <path
        fill="currentColor"
        d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"
      />
    </svg>
  )
}

function StaticRoute() {
  return (
    <section id="how" className="mx-auto w-full max-w-md scroll-mt-24 px-4 py-16">
      <SectionLabel />
      <ol aria-label="Шаги поездки" className="mt-8 flex list-none flex-col gap-6 border-l-2 border-dashed border-highlight/25 pl-6">
        {STOPS.map((stop, i) => (
          <li key={stop.title} className="relative">
            <span aria-hidden className="absolute -left-[33px] top-7 h-4 w-4 rounded-full bg-highlight ring-4 ring-background" />
            <StopCard index={i} stop={stop} className="w-full" />
          </li>
        ))}
      </ol>
      <Arrival className="mt-12" />
    </section>
  )
}

function Flight() {
  const section = useRef<HTMLElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const world = useRef<HTMLDivElement>(null)
  const far = useRef<HTMLDivElement>(null)
  const plane = useRef<HTMLDivElement>(null)
  const trail = useRef<SVGPathElement>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const layout = flightLayout(size.w)
  const points = useMemo(
    () => layout.waypoints.map((p) => ({ x: p.x * size.w, y: p.y * size.h })),
    [layout, size],
  )
  const route = useMemo(() => (size.w ? buildRoute(points) : null), [points, size.w])

  useLayoutEffect(() => {
    const el = stage.current!
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!route) return
    const visited = route.stops.slice(1)
    const legs = visited.length - 1
    const cards = [...section.current!.querySelectorAll<HTMLElement>('[data-stop]')]
    let docked: number | null = null

    const render = (progress: number) => {
      const f = travel(progress, visited)
      const p = route.at(f)
      const camera = cameraAt(progress, layout)
      const cx = size.w * camera.x - p.x
      const cy = size.h * camera.y - p.y
      world.current!.style.transform = `translate3d(${cx}px, ${cy}px, 0)`
      far.current!.style.transform = `translate3d(${cx * PARALLAX}px, ${cy * PARALLAX}px, 0)`
      plane.current!.style.transform = `translate3d(${p.x}px, ${p.y}px, 0) translate(-50%, -50%) rotate(${p.angle + 90}deg)`
      trail.current!.style.strokeDashoffset = String(route.length * (1 - f))
      const now = dockedAt(progress, legs)
      if (now === docked) return
      docked = now
      cards.forEach((card) => card.toggleAttribute('data-active', Number(card.dataset.stop) === now))
      plane.current!.toggleAttribute('data-landed', now === legs)
    }

    const state = { progress: 0 }
    const tween = gsap.to(state, {
      progress: 1,
      ease: 'none',
      onUpdate: () => render(state.progress),
      scrollTrigger: { trigger: section.current, start: 'top top', end: 'bottom bottom', scrub: 0.8 },
    })
    tween.progress(tween.scrollTrigger?.progress ?? 0)
    render(state.progress)
    return () => {
      tween.scrollTrigger?.kill()
      tween.kill()
    }
  }, [layout, route, size])

  return (
    <section ref={section} id="how" data-testid="trip-flight" className="relative h-[420vh] scroll-mt-0">
      <div ref={stage} className="sticky top-0 h-svh overflow-clip">
        <SectionLabel className="absolute left-1/2 top-24 z-10 -translate-x-1/2" />
        <div ref={far} aria-hidden className="absolute left-0 top-0 will-change-transform">
          {points.slice(1).map((p, i) => (
            <span
              key={i}
              className={cn(
                'absolute h-[46vh] w-[46vh] -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl',
                i % 2 ? 'bg-highlight/10' : 'bg-primary/35',
              )}
              style={{
                left: p.x * PARALLAX + size.w * layout.plane.x * (1 - PARALLAX) + (i % 2 ? -1 : 1) * size.w * 0.18,
                top: p.y * PARALLAX + size.h * layout.plane.y * (1 - PARALLAX),
              }}
            />
          ))}
        </div>
        <div ref={world} className="absolute left-0 top-0 will-change-transform">
          {route && (
            <svg aria-hidden width={1} height={1} className="absolute left-0 top-0 overflow-visible">
              <path d={route.d} fill="none" stroke="var(--highlight)" strokeOpacity={0.25} strokeWidth={2.5} strokeLinecap="round" strokeDasharray="0.1 14" />
              <path ref={trail} d={route.d} fill="none" stroke="var(--highlight)" strokeWidth={3} strokeLinecap="round" strokeDasharray={route.length} />
            </svg>
          )}
          {STOPS.map((stop, i) => (
            <div key={stop.title} className="absolute" style={{ left: points[i + 1].x, top: points[i + 1].y }}>
              <StopCard
                index={i}
                stop={stop}
                className={cn(
                  'absolute scale-95 transition-[opacity,scale] duration-500 data-active:scale-100 data-active:opacity-100',
                  layout.compact ? 'opacity-0' : 'opacity-40',
                  layout.compact
                    ? 'left-1/2 top-12 w-[min(22rem,calc(100vw-2rem))] -translate-x-1/2'
                    : i % 2
                      ? 'right-12 top-10'
                      : 'bottom-10 left-12',
                )}
              />
            </div>
          ))}
          <div className="absolute" style={{ left: points[STOPS.length + 1].x, top: points[STOPS.length + 1].y }}>
            <Arrival
              className={cn(
                'absolute w-max -translate-x-1/2 scale-95 transition-[opacity,scale] duration-500 data-active:scale-100 data-active:opacity-100',
                layout.compact ? '-translate-y-40 opacity-0' : '-translate-y-36 opacity-40',
              )}
            />
          </div>
          <div ref={plane} className="absolute left-0 top-0 transition-opacity duration-300 data-landed:opacity-0">
            <Plane />
          </div>
        </div>
      </div>
    </section>
  )
}

/** «Как это работает»: on wide screens a plane flies a diagonal route through the steps as you scroll. */
export function TripRoute() {
  return useMediaQuery(FLIGHT_QUERY) ? <Flight /> : <StaticRoute />
}
