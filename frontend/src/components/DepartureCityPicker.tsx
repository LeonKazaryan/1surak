import { useState } from 'react'
import { MapPinIcon } from '@heroicons/react/24/outline'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DEPARTURE_CITIES, findDepartureCity, getDepartureCity, saveDepartureCity } from '@/lib/departureCity'

export function DepartureCityPicker() {
  const [city, setCity] = useState(getDepartureCity)

  const choose = (code: string) => {
    saveDepartureCity(code)
    setCity(findDepartureCity(code))
  }

  return (
    <Select value={city.code} onValueChange={choose}>
      <SelectTrigger
        size="sm"
        aria-label={`Город вылета: ${city.name}`}
        className="h-8 w-auto gap-1 rounded-full border-transparent bg-secondary/60 px-2.5 text-muted-foreground hover:bg-secondary"
      >
        <MapPinIcon className="h-3.5 w-3.5 shrink-0 text-highlight" />
        <SelectValue>{city.short ?? city.name}</SelectValue>
      </SelectTrigger>
      <SelectContent align="end" className="max-h-72">
        {DEPARTURE_CITIES.map((option) => (
          <SelectItem key={option.code} value={option.code}>
            {option.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
