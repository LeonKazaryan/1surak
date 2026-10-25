import type { RouteStop, TripKind } from '@/types/api'

/** A different scene for neighbouring cities, so two city stops do not look like one long skyline.
 *  Stops with the fewest kinds choose first: Samarkand is only a city, so Almaty shows its mountains. */
export function sceneKinds(stops: RouteStop[]): TripKind[] {
  const kinds: (TripKind | undefined)[] = stops.map(() => undefined)
  const order = stops.map((_, i) => i).sort((a, b) => stops[a].kinds.length - stops[b].kinds.length)
  for (const i of order) {
    const taken = [kinds[i - 1], kinds[i + 1]]
    kinds[i] = stops[i].kinds.find((k) => !taken.includes(k)) ?? stops[i].kinds[0] ?? 'city'
  }
  return kinds as TripKind[]
}
