import { DOT_STEP, LAND_ROWS } from './landDots'

/** A point on the globe, in degrees. */
export interface LatLon {
  lat: number
  lon: number
}

/** What part of the world a map shows, and how a point lands on it: x = lon × k (k evens out the
 * stretching of the plain lat/lon grid at the frame's latitude), y = −lat. */
export interface Frame {
  minLon: number
  maxLon: number
  minLat: number
  maxLat: number
  k: number
}

const RAD = Math.PI / 180

/** A longitude moved by whole turns to be nearest to `ref`: Almaty → Honolulu goes east over the Pacific. */
export function unwrap(lon: number, ref: number): number {
  let x = lon
  while (x - ref > 180) x -= 360
  while (x - ref < -180) x += 360
  return x
}

/** Points along the great circle from a to b, longitudes kept continuous from a. */
export function greatCircle(a: LatLon, b: LatLon, steps = 48): LatLon[] {
  const [φ1, λ1, φ2, λ2] = [a.lat * RAD, a.lon * RAD, b.lat * RAD, b.lon * RAD]
  const d = 2 * Math.asin(Math.sqrt(Math.sin((φ2 - φ1) / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin((λ2 - λ1) / 2) ** 2))
  if (d < 1e-6) return [a, b]
  const points: LatLon[] = []
  let previous = a.lon
  for (let i = 0; i <= steps; i++) {
    const f = i / steps
    const A = Math.sin((1 - f) * d) / Math.sin(d)
    const B = Math.sin(f * d) / Math.sin(d)
    const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2)
    const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2)
    const z = A * Math.sin(φ1) + B * Math.sin(φ2)
    const lon = unwrap(Math.atan2(y, x) / RAD, previous)
    previous = lon
    points.push({ lat: Math.atan2(z, Math.hypot(x, y)) / RAD, lon })
  }
  return points
}

/** The middle of these longitudes on the circle: the US cities' middle is −91°, not the average of
 * −74 and 245. */
export function middleLon(lons: number[]): number {
  if (!lons.length) return 0
  const x = lons.reduce((sum, lon) => sum + Math.cos(lon * RAD), 0)
  const y = lons.reduce((sum, lon) => sum + Math.sin(lon * RAD), 0)
  return Math.atan2(y, x) / RAD
}

/** A flight drawn as a bridge from a to b, bowed upwards as on a departures board: a true great circle on this
 * flat map would climb to the Arctic and back. Returns the three points of a quadratic curve. */
export function bridge(a: LatLon, b: LatLon, k: number): [LatLon, LatLon, LatLon] {
  const [x0, y0, x1, y1] = [a.lon * k, a.lat, b.lon * k, b.lat]
  const length = Math.hypot(x1 - x0, y1 - y0)
  const bow = Math.min(length * 0.26, 28)
  // the normal that points north, so every bridge bows the same way
  let [nx, ny] = [-(y1 - y0) / (length || 1), (x1 - x0) / (length || 1)]
  if (ny < 0) [nx, ny] = [-nx, -ny]
  const control = { lon: ((x0 + x1) / 2 + nx * bow) / k, lat: (y0 + y1) / 2 + ny * bow }
  return [a, control, b]
}

export function curveThrough(f: Frame, [a, c, b]: [LatLon, LatLon, LatLon]): string {
  return `M${round(a.lon * f.k)} ${round(-a.lat)}Q${round(c.lon * f.k)} ${round(-c.lat)} ${round(b.lon * f.k)} ${round(-b.lat)}`
}

/** The frame that shows all these points with some air, at this width-to-height ratio. A frame is never
 * narrower than `minSpan` degrees: one city alone still shows its region. */
export function frameAround(points: LatLon[], aspect: number, pad = 0.18, minSpan = 18): Frame {
  const lats = points.map((p) => p.lat)
  const lons = points.map((p) => p.lon)
  let [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)]
  let [minLon, maxLon] = [Math.min(...lons), Math.max(...lons)]
  const midLat = (minLat + maxLat) / 2
  const k = Math.max(0.55, Math.cos(midLat * RAD))
  let spanLon = Math.max(maxLon - minLon, minSpan) * (1 + pad * 2)
  let spanLat = Math.max(maxLat - minLat, minSpan / 2) * (1 + pad * 2)
  // the frame keeps the box's shape: widen or heighten whichever is short
  if ((spanLon * k) / spanLat < aspect) spanLon = (aspect * spanLat) / k
  else spanLat = (spanLon * k) / aspect
  const midLon = (minLon + maxLon) / 2
  ;[minLon, maxLon] = [midLon - spanLon / 2, midLon + spanLon / 2]
  ;[minLat, maxLat] = [midLat - spanLat / 2, midLat + spanLat / 2]
  return { minLon, maxLon, minLat, maxLat, k }
}

/** The whole world the land data covers, for a backdrop. */
export const WORLD: Frame = { minLon: -180, maxLon: 180, minLat: -56, maxLat: 83, k: 1 }

export function viewBox(f: Frame): string {
  return `${round(f.minLon * f.k)} ${round(-f.maxLat)} ${round((f.maxLon - f.minLon) * f.k)} ${round(f.maxLat - f.minLat)}`
}

/** Where a point is on the frame, as fractions of its width and height (for HTML laid over the SVG). */
export function place(f: Frame, p: LatLon): { x: number; y: number } {
  return { x: (p.lon - f.minLon) / (f.maxLon - f.minLon), y: (f.maxLat - p.lat) / (f.maxLat - f.minLat) }
}

export function pathThrough(f: Frame, points: LatLon[]): string {
  return points.map((p, i) => `${i ? 'L' : 'M'}${round(p.lon * f.k)} ${round(-p.lat)}`).join('')
}

function round(n: number): number {
  return Math.round(n * 100) / 100
}

/** The land inside the frame as dots: one subpath per run of land on a latitude, drawn with a dash pattern
 * of zero-length dashes and round caps, so the whole map is a single path element. `every` thins the
 * dots out on a wide frame. */
export function landDots(f: Frame, every = 1): { d: string; gap: number; size: number } {
  const step = DOT_STEP * every
  const parts: string[] = []
  for (const [lat, runs] of LAND_ROWS) {
    if (lat < f.minLat - DOT_STEP || lat > f.maxLat + DOT_STEP) continue
    if (every > 1 && Math.round(lat / DOT_STEP) % every !== 0) continue
    for (const shift of [-360, 0, 360]) {
      for (let i = 0; i < runs.length; i += 2) {
        const start = runs[i] + shift
        const count = runs[i + 1]
        const end = start + count * DOT_STEP
        if (end < f.minLon - step || start > f.maxLon + step) continue
        // the dots of this run inside the frame, on the coarser grid when thinned
        const first = Math.max(Math.ceil((Math.max(start, f.minLon - step) - start) / step), 0)
        const last = Math.min(Math.floor((Math.min(end, f.maxLon + step) - start - DOT_STEP / 2) / step), Math.floor((count - 1) / every))
        if (first > last) continue
        const x = (start + DOT_STEP / 2 + first * step) * f.k
        parts.push(`M${round(x)} ${round(-lat)}h${round((last - first) * step * f.k)}`)
      }
    }
  }
  return { d: parts.join(''), gap: round(step * f.k), size: round(step * f.k * 0.52) }
}
