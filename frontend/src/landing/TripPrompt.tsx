import { useState } from 'react'
import { ArrowRightIcon, XMarkIcon } from '@heroicons/react/20/solid'
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { cn } from '@/components/ui/utils'

interface TripPromptProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
}

export function TripPrompt({ value, onChange, onSubmit }: TripPromptProps) {
  const [focused, setFocused] = useState(false)

  return (
    <div className="relative">
      <div
        aria-hidden
        className={cn(
          'pointer-events-none absolute -inset-3 -z-10 rounded-[1.75rem] bg-gradient-to-r from-primary/50 via-highlight/10 to-primary/30 blur-2xl transition-opacity duration-500',
          focused ? 'opacity-90' : 'opacity-50',
        )}
      />
      <form
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit()
        }}
        className={cn(
          'relative flex items-center gap-3 rounded-2xl border bg-white px-4 py-3 shadow-sm transition-all duration-300',
          focused ? 'border-highlight/40 shadow-xl ring-4 ring-primary/25' : 'border-border hover:border-highlight/30 hover:shadow-md',
        )}
      >
        <MagnifyingGlassIcon aria-hidden className="h-5 w-5 shrink-0 text-highlight" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          aria-label="Опишите поездку"
          placeholder="Куда хотите поехать?"
          className="min-w-0 flex-1 bg-transparent text-base text-foreground outline-none placeholder:text-faint"
        />
        {value && (
          <button
            type="button"
            aria-label="Очистить"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => onChange('')}
            className="flex shrink-0 items-center justify-center rounded-full bg-secondary p-1 text-muted-foreground transition-colors hover:bg-border hover:text-foreground"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        )}
        <button
          type="submit"
          aria-label="Спланировать"
          className="flex min-h-[38px] shrink-0 items-center rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary-hover sm:px-5"
        >
          <span className="hidden sm:inline">Спланировать</span>
          <ArrowRightIcon className="h-4 w-4 sm:hidden" aria-hidden />
        </button>
      </form>
    </div>
  )
}
