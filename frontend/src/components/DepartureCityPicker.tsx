import { useEffect, useState } from 'react'
import { Popover } from 'radix-ui'
import { MagnifyingGlassIcon, MapPinIcon } from '@heroicons/react/24/outline'
import { cn } from '@/components/ui/utils'
import {
  detectCity,
  getDepartureCity,
  nearbyCities,
  saveDepartureCity,
  savedDepartureCity,
  searchCities,
  type DepartureCity,
} from '@/lib/departureCity'

const SEARCH_DELAY_MS = 250

function CityRow({ city, active, note, onPick }: { city: DepartureCity; active: boolean; note?: string; onPick: () => void }) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onPick}
      className={cn(
        'flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent',
        active && 'bg-accent font-medium',
      )}
    >
      <span className="min-w-0 truncate">
        {city.name}
        {city.country && <span className="text-muted-foreground"> · {city.country}</span>}
      </span>
      <span className="shrink-0 text-[11px] text-faint">{note ?? city.code}</span>
    </button>
  )
}

/** Departure city: detected from the IP on the first visit, searchable across every city Aviasales flies from. */
export function DepartureCityPicker() {
  const [city, setCity] = useState(getDepartureCity)
  const [here, setHere] = useState<DepartureCity | null>(null)
  const [open, setOpen] = useState(false)
  const [term, setTerm] = useState('')
  const [found, setFound] = useState<DepartureCity[] | null>(null)
  const [nearby, setNearby] = useState<DepartureCity[]>([])

  useEffect(() => {
    const controller = new AbortController()
    detectCity(controller.signal)
      .then(async (detected) => {
        if (!detected) return
        setHere(detected)
        if (!savedDepartureCity()) {
          saveDepartureCity(detected)
          setCity(detected)
        }
        if (detected.lat !== undefined && detected.lon !== undefined) {
          setNearby(await nearbyCities(detected.lat, detected.lon, controller.signal))
        }
      })
      .catch(() => {}) // offline or blocked: the saved city stays, and search still works
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const query = term.trim()
    if (query.length < 2) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchCities(query, controller.signal)
        .then(setFound)
        .catch(() => {})
    }, SEARCH_DELAY_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [term])

  const choose = (picked: DepartureCity) => {
    saveDepartureCity(picked)
    setCity(picked)
    setOpen(false)
    setTerm('')
    setFound(null)
  }

  const searching = term.trim().length >= 2
  const suggestions = nearby.filter((c) => c.code !== here?.code)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger
        aria-label={`Город вылета: ${city.name}`}
        className="inline-flex h-8 items-center gap-1 rounded-full bg-secondary/60 px-2.5 text-sm text-muted-foreground transition-colors hover:bg-secondary"
      >
        <MapPinIcon className="h-3.5 w-3.5 shrink-0 text-highlight" />
        {city.name}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          className="z-50 w-72 rounded-2xl border border-border bg-card p-2 shadow-[0_20px_50px_-24px_rgba(15,23,42,0.45)]"
        >
          <label className="flex items-center gap-2 rounded-xl bg-secondary/70 px-3 py-2">
            <MagnifyingGlassIcon className="h-4 w-4 text-faint" />
            <input
              autoFocus
              value={term}
              onChange={(e) => {
                setTerm(e.target.value)
                setFound(null)
              }}
              placeholder="Откуда летите?"
              aria-label="Поиск города вылета"
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-faint"
            />
          </label>
          <div role="listbox" aria-label="Города вылета" className="mt-1.5 max-h-72 overflow-y-auto">
            {searching ? (
              found === null ? (
                <p className="m-0 px-2.5 py-3 text-sm text-muted-foreground">Ищу…</p>
              ) : found.length ? (
                found.map((c) => <CityRow key={c.code} city={c} active={c.code === city.code} onPick={() => choose(c)} />)
              ) : (
                <p className="m-0 px-2.5 py-3 text-sm text-muted-foreground">Такого города не нашлось</p>
              )
            ) : (
              <>
                {here && <CityRow city={here} active={here.code === city.code} note="рядом с вами" onPick={() => choose(here)} />}
                {suggestions.length > 0 ? (
                  <p className="m-0 px-2.5 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-faint uppercase">Ближайшие</p>
                ) : (
                  !here && <p className="m-0 px-2.5 py-3 text-sm text-muted-foreground">Начните вводить город</p>
                )}
                {suggestions.map((c) => (
                  <CityRow key={c.code} city={c} active={c.code === city.code} onPick={() => choose(c)} />
                ))}
              </>
            )}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
