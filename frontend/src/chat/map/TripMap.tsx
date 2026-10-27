import { useMemo } from 'react'
import { motion } from 'motion/react'
import { cn } from '@/components/ui/utils'
import { flagEmoji } from '../widgets'
import { bridge, curveThrough, frameAround, landDots, middleLon, pathThrough, place, unwrap, viewBox, type LatLon } from './geo'

export interface MapPin extends LatLon {
  id: string
  name: string
  countryCode?: string
  /** Shown when the pin is active: «от 12 000 ₸». */
  note?: string
}

export interface MapRoute {
  id: string
  /** The stops in travel order; the route starts and ends at home when there is one. */
  stops: (LatLon & { name: string })[]
  /** How each leg goes, home → first stop first; a missing one flies. */
  modes?: ('flight' | 'ground')[]
}

interface TripMapProps {
  origin?: (LatLon & { name: string }) | null
  pins?: MapPin[]
  routes?: MapRoute[]
  /** The card the user points at: its arc and pin light up. */
  active?: string | null
  onActive?: (id: string | null) => void
  onSelect?: (id: string) => void
  aspect?: number
  className?: string
}

const ARC_DELAY = 0.45
const ARC_STAGGER = 0.22
const ARC_DRAW = 0.9

interface Arc {
  id: string
  d: string
  ground: boolean
  order: number
}

/** The trip on a dotted map of the world: home, the places on the cards and the way to each, drawn in turn. */
export function TripMap({ origin, pins = [], routes = [], active = null, onActive, onSelect, aspect = 2.7, className }: TripMapProps) {
  // the places keep together around their middle, home joins them the short way: Almaty sits right of the US
  const lons = [...pins.map((p) => p.lon), ...routes.flatMap((r) => r.stops.map((s) => s.lon))]
  const ref = lons.length ? middleLon(lons) : (origin?.lon ?? 0)
  const home = origin ? { ...origin, lon: unwrap(origin.lon, ref) } : null
  const spots = pins.map((p) => ({ ...p, lon: unwrap(p.lon, ref) }))
  const ways = routes.map((r) => ({ ...r, stops: r.stops.map((s) => ({ ...s, lon: unwrap(s.lon, ref) })) }))

  const { frame, arcs, dots } = useMemo(() => {
    const ends = [...(home ? [home] : []), ...spots, ...ways.flatMap((r) => r.stops)]
    const k = frameAround(ends.length ? ends : [{ lat: 30, lon: 40 }], aspect).k
    const lines: { id: string; points: [LatLon, LatLon, LatLon] | LatLon[]; ground: boolean }[] = []
    if (home) spots.forEach((p) => lines.push({ id: p.id, points: bridge(home, p, k), ground: false }))
    for (const r of ways) {
      const chain = home ? [home, ...r.stops, home] : r.stops
      chain.slice(1).forEach((to, i) => {
        const ground = r.modes?.[i] === 'ground'
        lines.push({ id: r.id, points: ground ? [chain[i], to] : bridge(chain[i], to, k), ground })
      })
    }
    // the bridges' tops are in the frame too, else a long one leaves the map
    const all = [...ends, ...lines.flatMap((l) => l.points)]
    const frame = frameAround(all.length ? all : [{ lat: 30, lon: 40 }], aspect)
    const wide = frame.maxLon - frame.minLon > 110
    return {
      frame,
      dots: landDots(frame, wide ? 2 : 1),
      arcs: lines.map(
        (l, i): Arc => ({
          id: l.id,
          d: l.points.length === 3 ? curveThrough(frame, l.points as [LatLon, LatLon, LatLon]) : pathThrough(frame, l.points),
          ground: l.ground,
          order: i,
        }),
      ),
    }
    // the shape of the trip, not the identity of the arrays
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify([home, spots.map((p) => [p.id, p.lat, p.lon]), ways.map((r) => r.stops.map((s) => [s.lat, s.lon]))]), aspect])

  const width = (frame.maxLon - frame.minLon) * frame.k
  const stroke = width / 320
  const routeStops = ways.flatMap((r) => r.stops.map((s, i) => ({ ...s, id: `${r.id}-${i}`, route: r.id, order: i })))

  return (
    <div
      className={cn(
        'relative isolate overflow-hidden rounded-2xl border border-border bg-[radial-gradient(120%_90%_at_20%_10%,#f5fbef_0%,#f3f7fd_55%,#eef3fa_100%)]',
        className,
      )}
      style={{ aspectRatio: aspect }}
      role="img"
      aria-label={`Карта: ${[origin?.name, ...pins.map((p) => p.name), ...routes.flatMap((r) => r.stops.map((s) => s.name))].filter(Boolean).join(', ')}`}
    >
      <svg viewBox={viewBox(frame)} className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid meet" aria-hidden>
        <motion.path
          d={dots.d}
          fill="none"
          stroke="#aebccb"
          strokeWidth={dots.size}
          strokeLinecap="round"
          strokeDasharray={`0 ${dots.gap}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
        {arcs.map((arc) => {
          const lit = active === null || active === arc.id
          const delay = ARC_DELAY + arc.order * ARC_STAGGER
          return (
            <g key={`${arc.id}-${arc.order}`} style={{ opacity: lit ? 1 : 0.22, transition: 'opacity 0.3s ease' }}>
              <motion.path
                d={arc.d}
                fill="none"
                stroke={arc.ground ? '#4c9a2a' : 'var(--highlight)'}
                strokeOpacity={arc.ground ? 0.85 : 0.55}
                strokeWidth={active === arc.id ? stroke * 1.7 : stroke}
                strokeLinecap="round"
                strokeDasharray={arc.ground ? `${stroke * 2.5} ${stroke * 2.5}` : undefined}
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: ARC_DRAW, delay, ease: [0.65, 0, 0.35, 1] }}
              />
              {!arc.ground && (
                <motion.path
                  d={arc.d}
                  fill="none"
                  stroke="var(--highlight)"
                  strokeWidth={stroke * 1.15}
                  strokeLinecap="round"
                  strokeDasharray={`${stroke * 3} ${stroke * 14}`}
                  className="arc-flow"
                  style={{ ['--flow' as string]: `${stroke * 17}px` }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.9 }}
                  transition={{ duration: 0.4, delay: delay + ARC_DRAW }}
                />
              )}
            </g>
          )
        })}
      </svg>

      {home && (
        <Pin at={place(frame, home)} delay={0.25} label={home.name} kind="home" showLabel />
      )}
      {spots.map((p, i) => (
        <Pin
          key={p.id}
          at={place(frame, p)}
          delay={ARC_DELAY + i * ARC_STAGGER + ARC_DRAW * (home ? 0.85 : 0)}
          label={`${p.countryCode ? `${flagEmoji(p.countryCode)} ` : ''}${p.name}`}
          note={p.note}
          kind="place"
          active={active === p.id}
          dim={active !== null && active !== p.id}
          below={i % 2 === 1}
          showLabel
          onEnter={() => onActive?.(p.id)}
          onLeave={() => onActive?.(null)}
          onClick={() => onSelect?.(p.id)}
        />
      ))}
      {routeStops.map((s, i) => (
        <Pin
          key={s.id}
          at={place(frame, s)}
          delay={ARC_DELAY + i * ARC_STAGGER + ARC_DRAW * 0.85}
          label={`${s.order + 1}. ${s.name}`}
          kind="stop"
          active={active === s.route}
          dim={active !== null && active !== s.route}
          below={i % 2 === 1}
          showLabel={active === s.route || routes.length === 1}
          onEnter={() => onActive?.(s.route)}
          onLeave={() => onActive?.(null)}
          onClick={() => onSelect?.(s.route)}
        />
      ))}
    </div>
  )
}

interface PinProps {
  at: { x: number; y: number }
  delay: number
  label: string
  note?: string
  kind: 'home' | 'place' | 'stop'
  active?: boolean
  dim?: boolean
  below?: boolean
  showLabel?: boolean
  onEnter?: () => void
  onLeave?: () => void
  onClick?: () => void
}

function Pin({ at, delay, label, note, kind, active, dim, below, showLabel, onEnter, onLeave, onClick }: PinProps) {
  const home = kind === 'home'
  return (
    <motion.div
      className="absolute z-10"
      style={{ left: `${at.x * 100}%`, top: `${at.y * 100}%` }}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: dim ? 0.55 : 1 }}
      transition={{ type: 'spring', stiffness: 460, damping: 20, delay }}
    >
      <button
        type="button"
        tabIndex={home ? -1 : 0}
        onMouseEnter={onEnter}
        onMouseLeave={onLeave}
        onFocus={onEnter}
        onBlur={onLeave}
        onClick={onClick}
        aria-label={label}
        className={cn('group absolute -translate-x-1/2 -translate-y-1/2 outline-none', home && 'pointer-events-none')}
      >
        {home && <span className="absolute inset-0 -m-2 animate-ping rounded-full bg-highlight/30 [animation-duration:2.4s]" />}
        <span
          className={cn(
            'relative block rounded-full ring-2 ring-white shadow-[0_2px_6px_rgba(15,23,42,0.25)] transition-transform duration-300',
            home ? 'h-3 w-3 bg-highlight' : kind === 'stop' ? 'h-2.5 w-2.5 bg-[#4c9a2a]' : 'h-3 w-3 bg-primary',
            active && 'scale-150',
            !home && 'group-hover:scale-150 group-focus-visible:scale-150',
          )}
        />
      </button>
      {(showLabel || active) && (
        <motion.span
          initial={{ opacity: 0, y: below ? -3 : 3 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: delay + 0.1, duration: 0.3 }}
          className={cn(
            'pointer-events-none absolute left-0 -translate-x-1/2 rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap shadow-sm backdrop-blur-sm transition-colors',
            below ? 'top-2.5' : 'bottom-2.5',
            home ? 'bg-highlight text-white' : active ? 'bg-foreground text-white' : 'bg-white/90 text-foreground',
          )}
        >
          {label}
          {active && note && <span className="ml-1 font-medium text-white/75">· {note}</span>}
        </motion.span>
      )}
    </motion.div>
  )
}
