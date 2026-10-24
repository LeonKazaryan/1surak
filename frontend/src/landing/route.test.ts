import { describe, expect, it } from 'vitest'
import { buildRoute, cameraAt, dockedAt, flightLayout, travel } from './route'

const WAYPOINTS = [
  { x: 0, y: 0 },
  { x: 100, y: 60 },
  { x: 220, y: 150 },
  { x: 300, y: 260 },
]

describe('buildRoute', () => {
  it('should start at the first waypoint and end at the last', () => {
    const route = buildRoute(WAYPOINTS)

    expect(route.at(0)).toMatchObject({ x: 0, y: 0 })
    expect(route.at(1)).toMatchObject({ x: 300, y: 260 })
  })

  it('should pass through every waypoint in order', () => {
    const route = buildRoute(WAYPOINTS)

    expect(route.stops).toHaveLength(WAYPOINTS.length)
    expect([...route.stops].sort((a, b) => a - b)).toEqual(route.stops)
    route.stops.forEach((f, i) => {
      expect(route.at(f).x).toBeCloseTo(WAYPOINTS[i].x, 0)
      expect(route.at(f).y).toBeCloseTo(WAYPOINTS[i].y, 0)
    })
  })

  it('should point along the direction of travel', () => {
    expect(buildRoute([{ x: 0, y: 0 }, { x: 100, y: 0 }]).at(0.5).angle).toBeCloseTo(0)
    expect(buildRoute([{ x: 0, y: 0 }, { x: 0, y: 100 }]).at(0.5).angle).toBeCloseTo(90)
  })

  it('should clamp progress outside the route', () => {
    const route = buildRoute(WAYPOINTS)

    expect(route.at(-1)).toEqual(route.at(0))
    expect(route.at(2)).toEqual(route.at(1))
  })

  it('should draw the route as one svg path', () => {
    expect(buildRoute(WAYPOINTS).d).toMatch(/^M0 0L/)
  })

  it('should need at least two waypoints', () => {
    expect(() => buildRoute([{ x: 0, y: 0 }])).toThrow()
  })
})

describe('travel', () => {
  const stops = [0.1, 0.4, 0.7, 1]

  it('should rest at each stop and fly between them', () => {
    expect(travel(0, stops)).toBeCloseTo(0.1)
    expect(travel(1 / 3, stops)).toBeCloseTo(0.4)
    expect(travel(1, stops)).toBeCloseTo(1)
    expect(travel(0.5 / 3, stops)).toBeGreaterThan(0.1)
    expect(travel(0.5 / 3, stops)).toBeLessThan(0.4)
  })
})

describe('dockedAt', () => {
  it('should name the stop the plane rests at, or none while it flies', () => {
    expect(dockedAt(0, 3)).toBe(0)
    expect(dockedAt(1 / 3, 3)).toBe(1)
    expect(dockedAt(0.5 / 3, 3)).toBe(-1)
    expect(dockedAt(1, 3)).toBe(3)
  })
})

describe('flightLayout', () => {
  it('should zigzag down the screen on phones so every stop stays in view', () => {
    const { compact, waypoints } = flightLayout(390)
    const stops = waypoints.slice(1)

    expect(compact).toBe(true)
    stops.forEach(({ x }) => {
      expect(x).toBeGreaterThanOrEqual(0)
      expect(x).toBeLessThanOrEqual(1)
    })
    stops.slice(1).forEach(({ y }, i) => expect(y).toBeGreaterThan(stops[i].y))
  })

  it('should sweep diagonally past the screen on wide screens', () => {
    const { compact, waypoints } = flightLayout(1440)

    expect(compact).toBe(false)
    expect(waypoints[waypoints.length - 1].x).toBeGreaterThan(2)
  })
})

describe('cameraAt', () => {
  it('should keep the plane at its usual spot until the last leg', () => {
    const layout = flightLayout(390)

    expect(cameraAt(0, layout)).toEqual(layout.plane)
    expect(cameraAt(0.5, layout)).toEqual(layout.plane)
  })

  it('should ease the beach lower on phones so it lands close to the footer', () => {
    const layout = flightLayout(390)

    expect(layout.landing.y).toBeGreaterThan(layout.plane.y)
    expect(cameraAt(1, layout)).toEqual(layout.landing)
  })
})
