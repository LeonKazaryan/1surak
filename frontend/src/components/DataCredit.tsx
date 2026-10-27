import { Fragment } from 'react'
import { cn } from '@/components/ui/utils'
import type { DataSource } from '@/lib/dataSources'

/** Open data we show, credited as its licence asks: OSM (ODbL), Open-Meteo (CC BY 4.0), Google's listings. */
const SOURCES: Record<DataSource, { label: string; href: string }> = {
  osm: { label: '© участники OpenStreetMap', href: 'https://www.openstreetmap.org/copyright' },
  openMeteo: { label: 'Open-Meteo', href: 'https://open-meteo.com/' },
  google: { label: 'Google Maps', href: 'https://www.google.com/maps' },
}

export function DataCredit({ sources, prefix = 'Данные:', className }: { sources: DataSource[]; prefix?: string; className?: string }) {
  if (!sources.length) return null
  return (
    <p className={cn('m-0 text-[11px] text-faint', className)}>
      {prefix}{' '}
      {sources.map((key, i) => (
        <Fragment key={key}>
          {i > 0 && ' · '}
          <a href={SOURCES[key].href} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
            {SOURCES[key].label}
          </a>
        </Fragment>
      ))}
    </p>
  )
}
