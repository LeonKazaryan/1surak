import { useEffect, useImperativeHandle, useLayoutEffect, useRef, useState, type Ref } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowUpIcon, MicrophoneIcon, StopIcon } from '@heroicons/react/20/solid'
import { cn } from '@/components/ui/utils'

export const MAX_CHAT_INPUT_CHARS = 12_000
const MAX_TEXTAREA_PX = 220
const SHOW_COUNTER_FROM = 10_000
const DESCRIBE_TRIP = 'Опишите поездку своими словами…'
const PLANE = 'M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z'

// The Web Speech API is not in every browser, nor in TypeScript's DOM types: just what the composer uses.
interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  start: () => void
  stop: () => void
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
}
type RecognitionClass = new () => Recognition

function speechRecognition(): RecognitionClass | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: RecognitionClass; webkitSpeechRecognition?: RecognitionClass }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled: boolean
  placeholder?: string
  /** The agent is answering: the send button becomes a stop button. */
  streaming?: boolean
  onStop?: () => void
  ref?: Ref<HTMLTextAreaElement>
}

export function Composer({ value, onChange, onSubmit, disabled, placeholder = DESCRIBE_TRIP, streaming = false, onStop, ref }: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  useImperativeHandle(ref, () => textareaRef.current!, [])
  const [multiline, setMultiline] = useState(false)
  const [planes, setPlanes] = useState<number[]>([])
  const [listening, setListening] = useState(false)
  const recognition = useRef<Recognition | null>(null)
  const Speech = speechRecognition()

  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const next = Math.min(Math.max(el.scrollHeight, 28), MAX_TEXTAREA_PX)
    el.style.height = `${next}px`
    setMultiline(next > 52)
  }, [value])

  useEffect(() => () => recognition.current?.stop(), [])

  const send = () => {
    if (disabled || !value.trim()) return
    recognition.current?.stop()
    setPlanes((p) => [...p, Date.now()])
    onSubmit()
  }

  const listen = () => {
    if (!Speech) return
    if (listening) {
      recognition.current?.stop()
      return
    }
    const r = new Speech()
    r.lang = 'ru-RU'
    r.interimResults = true
    r.continuous = false
    const before = value.trim() ? `${value.trim()} ` : ''
    r.onresult = (event) => {
      const heard = Array.from(event.results, (result) => result[0]?.transcript ?? '').join('')
      onChange(`${before}${heard}`.slice(0, MAX_CHAT_INPUT_CHARS))
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    recognition.current = r
    setListening(true)
    r.start()
    textareaRef.current?.focus()
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        className={cn(
          'relative flex gap-2 rounded-2xl border border-border bg-white px-4 py-3 shadow-sm transition-all duration-200 focus-within:border-highlight/40 focus-within:shadow-md focus-within:ring-4 focus-within:ring-primary/25',
          multiline ? 'items-end' : 'items-center',
          listening && 'border-primary ring-4 ring-primary/30',
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, MAX_CHAT_INPUT_CHARS))}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              send()
            }
          }}
          placeholder={listening ? 'Слушаю…' : placeholder}
          aria-label="Сообщение агенту"
          rows={1}
          maxLength={MAX_CHAT_INPUT_CHARS}
          className="max-h-[220px] min-w-0 flex-1 resize-none overflow-y-auto border-none bg-transparent py-0.5 text-[15px] leading-relaxed text-foreground outline-none placeholder:text-faint"
        />

        {Speech && !streaming && (
          <button
            type="button"
            onClick={listen}
            aria-label={listening ? 'Остановить запись' : 'Сказать голосом'}
            aria-pressed={listening}
            className={cn(
              'relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors',
              listening ? 'bg-primary text-primary-foreground' : 'text-faint hover:bg-secondary hover:text-foreground',
            )}
          >
            {listening && (
              <>
                <span aria-hidden className="listen-ring absolute inset-0 rounded-xl bg-primary" />
                <span aria-hidden className="listen-ring absolute inset-0 rounded-xl bg-primary [animation-delay:0.7s]" />
              </>
            )}
            <MicrophoneIcon className="relative h-4 w-4" />
          </button>
        )}

        <div className="relative h-9 w-9 shrink-0">
          <AnimatePresence initial={false} mode="popLayout">
            {streaming ? (
              <motion.button
                key="stop"
                type="button"
                onClick={onStop}
                aria-label="Остановить ответ"
                initial={{ scale: 0.6, opacity: 0, rotate: -90 }}
                animate={{ scale: 1, opacity: 1, rotate: 0 }}
                exit={{ scale: 0.6, opacity: 0, rotate: 90 }}
                transition={{ type: 'spring', stiffness: 460, damping: 26 }}
                className="absolute inset-0 flex items-center justify-center rounded-xl bg-foreground text-white"
              >
                <span aria-hidden className="absolute -inset-[3px] animate-spin rounded-[14px] bg-[conic-gradient(from_0deg,transparent_0deg,var(--primary)_120deg,transparent_240deg)] [animation-duration:1.6s]" />
                <span aria-hidden className="absolute inset-0 rounded-xl bg-foreground" />
                <StopIcon className="relative h-3.5 w-3.5" />
              </motion.button>
            ) : (
              <motion.button
                key="send"
                type="button"
                onClick={send}
                disabled={disabled || !value.trim()}
                aria-label="Отправить"
                initial={{ scale: 0.6, opacity: 0, rotate: 90 }}
                animate={{ scale: 1, opacity: 1, rotate: 0 }}
                exit={{ scale: 0.6, opacity: 0, rotate: -90 }}
                whileTap={{ scale: 0.9 }}
                transition={{ type: 'spring', stiffness: 460, damping: 26 }}
                className="absolute inset-0 flex items-center justify-center rounded-xl bg-primary text-primary-foreground transition-colors hover:bg-primary-hover disabled:bg-secondary disabled:text-faint"
              >
                <ArrowUpIcon className="h-4 w-4" />
              </motion.button>
            )}
          </AnimatePresence>
          {/* a paper plane takes the message away */}
          {planes.map((id) => (
            <motion.svg
              key={id}
              viewBox="0 0 24 24"
              aria-hidden
              className="pointer-events-none absolute top-1/2 left-1/2 z-20 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rotate-45 text-highlight"
              initial={{ x: 0, y: 0, opacity: 1, scale: 0.7 }}
              animate={{ x: 70, y: -90, opacity: 0, scale: 1.15 }}
              transition={{ duration: 0.75, ease: [0.25, 0.1, 0.25, 1] }}
              onAnimationComplete={() => setPlanes((p) => p.filter((x) => x !== id))}
            >
              <path fill="currentColor" d={PLANE} />
            </motion.svg>
          ))}
        </div>
      </div>
      {value.length > SHOW_COUNTER_FROM && (
        <p className="m-0 text-center text-[11px] text-faint tabular-nums">
          {value.length.toLocaleString('ru-RU')} / {MAX_CHAT_INPUT_CHARS.toLocaleString('ru-RU')}
        </p>
      )}
    </div>
  )
}
