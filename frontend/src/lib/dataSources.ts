export type DataSource = 'osm' | 'openMeteo' | 'google'

/** Where a place in a plan came from, by the id the backend gives it. */
export function spotSource(id: string | undefined): DataSource | null {
  if (id?.startsWith('osm-')) return 'osm'
  if (id?.startsWith('gp-')) return 'google'
  return null
}

export function fromOsm(url: string | null | undefined): boolean {
  return Boolean(url?.includes('openstreetmap.org'))
}
