import { useLayoutEffect, useRef, useState } from 'react'
import { ArrowUp } from 'lucide-react'
import { cn } from '@/components/ui/utils'

export const MAX_CHAT_INPUT_CHARS = 12_000
const MAX_TEXTAREA_PX = 220
const SHOW_COUNTER_FROM = 10_000

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled: boolean
}

export function Composer({ value, onChange, onSubmit, disabled }: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [multiline, setMultiline] = useState(false)

  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const next = Math.min(Math.max(el.scrollHeight, 28), MAX_TEXTAREA_PX)
    el.style.height = `${next}px`
    setMultiline(next > 52)
  }, [value])

  return (
    <div className="flex flex-col gap-2">
      <div
        className={cn(
          'flex gap-2 rounded-2xl border border-border bg-white px-4 py-3 shadow-sm transition-all duration-200 focus-within:border-highlight/40 focus-within:shadow-md focus-within:ring-4 focus-within:ring-primary/25',
          multiline ? 'items-end' : 'items-center',
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, MAX_CHAT_INPUT_CHARS))}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              onSubmit()
            }
          }}
          placeholder="Опишите поездку своими словами…"
          aria-label="Сообщение агенту"
          rows={1}
          maxLength={MAX_CHAT_INPUT_CHARS}
          className="max-h-[220px] min-w-0 flex-1 resize-none overflow-y-auto border-none bg-transparent py-0.5 text-[15px] leading-relaxed text-foreground outline-none placeholder:text-faint"
        />
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || !value.trim()}
          aria-label="Отправить"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-colors hover:bg-primary-hover disabled:bg-secondary disabled:text-faint"
        >
          <ArrowUp className="h-4 w-4" strokeWidth={2.5} />
        </button>
      </div>
      <p className="m-0 text-center text-[11px] text-faint">
        Прототип · бронирование и оплата имитируются
        {value.length > SHOW_COUNTER_FROM && (
          <span className="tabular-nums">
            {' '}
            · {value.length.toLocaleString('ru-RU')} / {MAX_CHAT_INPUT_CHARS.toLocaleString('ru-RU')}
          </span>
        )}
      </p>
    </div>
  )
}
