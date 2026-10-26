import type { GroundRide, RouteLeg } from '@/types/api'
import { shortDate } from './ticketFormat'

export type LegKind = 'flight' | 'train' | 'bus' | 'ground'

export const KIND_TONE: Record<LegKind, string> = {
  flight: 'bg-highlight/10 text-highlight',
  train: 'bg-primary/40 text-[#3f7d22]',
  bus: 'bg-amber-100 text-amber-700',
  ground: 'bg-primary/40 text-[#3f7d22]',
}
export const KIND_COLOR: Record<LegKind, string> = {
  flight: 'text-highlight',
  train: 'text-[#3f7d22]',
  bus: 'text-amber-700',
  ground: 'text-[#3f7d22]',
}

/** The flights and hops a leg is really made of: its parts, or the leg itself. */
export function units(leg: RouteLeg): RouteLeg[] {
  return leg.parts?.length ? leg.parts : [leg]
}

export function legKind(leg: RouteLeg): LegKind {
  if (leg.mode === 'flight') return 'flight'
  return leg.ground?.mode ?? 'ground'
}

/** A real fare for one flight or hop: the ticket, the train or bus; never the estimate by distance. */
export function fareOf(leg: RouteLeg): number | null {
  return leg.ticket?.price_rub ?? leg.ground?.price_rub ?? null
}

/** The real fares of the leg's parts together. */
export function knownFare(leg: RouteLeg): number | null {
  const fares = units(leg).map(fareOf)
  return fares.some((f) => f !== null) ? fares.reduce<number>((sum, f) => sum + (f ?? 0), 0) : null
}

/** How much a smarter way saves against the direct flight it replaced. */
export function saving(leg: RouteLeg): number | null {
  if (!leg.instead || leg.price_rub == null) return null
  const saved = leg.instead.price_rub - leg.price_rub
  return saved > 0 ? saved : null
}

/** Days the legs leave, in order: a smart way counts each of its tickets. */
export function travelDays(legs: RouteLeg[]): string[] {
  return legs.flatMap((leg) => units(leg).flatMap((p) => (p.ticket ? [shortDate(p.ticket.departure)] : [])))
}

function clockOf(value: string): string {
  return value.length > 5 ? value.slice(11, 16) : value
}

/** «16:49 → 19:04» from a timetable; a ride on its day also says the day: «15 ноя, 00:45 → 12:15». */
export function rideTimes(ride: GroundRide): string | null {
  if (!ride.departs) return null
  const times = [ride.departs, ride.arrives].filter(Boolean).map((t) => clockOf(t as string)).join(' → ')
  return ride.dated && ride.departs.length > 5 ? `${shortDate(ride.departs)}, ${times}` : times
}

/** Where to buy it: the shop's name for the button. */
export function rideShop(ride: GroundRide): string {
  return ride.link.includes('flixbus') ? 'FlixBus' : 'Туту.ру'
}

/** The city each leg brings you to, by the leg's `to_stop` (older cards without it count by order). */
export function stopIndexAfter(leg: RouteLeg, index: number, stops: number): number | null {
  if (leg.to_stop !== undefined) return leg.to_stop
  return index < stops ? index : null
}
