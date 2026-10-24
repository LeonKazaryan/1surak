export interface Point {
  x: number
  y: number
}

export interface RoutePoint extends Point {
  angle: number
}

export interface Route {
  d: string
  length: number
  stops: number[]
  at: (fraction: number) => RoutePoint
}

const SAMPLES_PER_LEG = 48
const DWELL = 0.2

const clamp01 = (x: number) => Math.min(1, Math.max(0, x))
const smooth = (x: number) => x * x * (3 - 2 * x)

function catmullRom(p0: Point, p1: Point, p2: Point, p3: Point, t: number): Point {
  const t2 = t * t
  const t3 = t2 * t
  const axis = (a: number, b: number, c: number, d: number) =>
    0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (3 * b - a - 3 * c + d) * t3)
  return { x: axis(p0.x, p1.x, p2.x, p3.x), y: axis(p0.y, p1.y, p2.y, p3.y) }
}

function sample(waypoints: Point[]): { points: Point[]; stopIndexes: number[] } {
  const points: Point[] = [waypoints[0]]
  const stopIndexes = [0]
  for (let i = 0; i < waypoints.length - 1; i++) {
    const before = waypoints[i - 1] ?? waypoints[i]
    const after = waypoints[i + 2] ?? waypoints[i + 1]
    for (let s = 1; s <= SAMPLES_PER_LEG; s++) {
      points.push(catmullRom(before, waypoints[i], waypoints[i + 1], after, s / SAMPLES_PER_LEG))
    }
    stopIndexes.push(points.length - 1)
  }
  return { points, stopIndexes }
}

/** A smooth curve through every waypoint, measured by arc length so the plane flies at an even speed. */
export function buildRoute(waypoints: Point[]): Route {
  if (waypoints.length < 2) throw new Error('A route needs at least two waypoints')
  const { points, stopIndexes } = sample(waypoints)
  const lengths = [0]
  for (let i = 1; i < points.length; i++) {
    lengths.push(lengths[i - 1] + Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y))
  }
  const length = lengths[lengths.length - 1]

  const at = (fraction: number): RoutePoint => {
    const target = clamp01(fraction) * length
    const i = Math.max(1, lengths.findIndex((l) => l >= target))
    const [a, b] = [points[i - 1], points[i]]
    const k = (target - lengths[i - 1]) / Math.max(1e-6, lengths[i] - lengths[i - 1])
    const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI
    return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, angle }
  }

  const d = points.map((p, i) => `${i ? 'L' : 'M'}${Math.round(p.x * 10) / 10} ${Math.round(p.y * 10) / 10}`).join('')
  return { d, length, stops: stopIndexes.map((i) => lengths[i] / length), at }
}

/** Scroll progress to a place on the route: rest at each stop, then ease to the next one. */
export function travel(progress: number, stops: number[]): number {
  const legs = stops.length - 1
  const u = clamp01(progress) * legs
  const leg = Math.min(legs - 1, Math.floor(u))
  const local = smooth(clamp01((u - leg - DWELL) / (1 - 2 * DWELL)))
  return stops[leg] + (stops[leg + 1] - stops[leg]) * local
}

/** The stop the plane is resting at for this scroll progress, or -1 while it is flying. */
export function dockedAt(progress: number, legs: number): number {
  const u = clamp01(progress) * legs
  const nearest = Math.round(u)
  return Math.abs(u - nearest) <= DWELL ? nearest : -1
}

export interface FlightLayout {
  compact: boolean
  waypoints: Point[]
  plane: Point
  landing: Point
}

const COMPACT_BELOW = 960
/** In viewport widths and heights: a lead-in, three stops and the beach. Wide screens weave down and to the right. */
const WIDE: FlightLayout = {
  compact: false,
  plane: { x: 0.5, y: 0.54 },
  landing: { x: 0.5, y: 0.54 },
  waypoints: [
    { x: -0.35, y: -0.2 },
    { x: 0.45, y: 0.45 },
    { x: 1.35, y: 0.85 },
    { x: 1.85, y: 1.75 },
    { x: 2.8, y: 2.2 },
  ],
}
/** Phones zigzag down the screen, so each card can sit centred under the plane. */
const COMPACT: FlightLayout = {
  compact: true,
  plane: { x: 0.5, y: 0.4 },
  landing: { x: 0.5, y: 0.66 },
  waypoints: [
    { x: 0.85, y: -0.35 },
    { x: 0.3, y: 0.4 },
    { x: 0.75, y: 1.2 },
    { x: 0.1, y: 2.05 },
    { x: 0.9, y: 2.2 },
  ],
}

export function flightLayout(width: number): FlightLayout {
  return width < COMPACT_BELOW ? COMPACT : WIDE
}

/** Where the plane sits on screen: its usual spot, easing to the landing spot while it flies the last leg. */
export function cameraAt(progress: number, layout: FlightLayout): Point {
  const legs = layout.waypoints.length - 2
  const k = smooth(clamp01((clamp01(progress) * legs - (legs - 1) - DWELL) / (1 - 2 * DWELL)))
  const { plane, landing } = layout
  return { x: plane.x + (landing.x - plane.x) * k, y: plane.y + (landing.y - plane.y) * k }
}
