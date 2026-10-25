import { motion } from 'motion/react'
import { CheckIcon } from '@heroicons/react/20/solid'
import type { ClarifyEvent } from '@/types/api'
import { plural } from '../widgets'
import { planCards } from './plan'

interface ClarifyPromptProps {
  widget: ClarifyEvent
  /** The questions still wait for answers: the chip reopens the cards. */
  pending: boolean
  onOpen: () => void
}

/** What stays in the chat for the question cards: a way back to them, or what was clarified. */
export function ClarifyPrompt({ widget, pending, onOpen }: ClarifyPromptProps) {
  const plans = planCards(widget)
  const labels = plans.map((p) => p.label.toLowerCase()).join(', ')

  if (!pending) {
    return (
      <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-card py-1.5 pr-3.5 pl-1.5 text-[13px] text-muted-foreground">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <CheckIcon className="h-3.5 w-3.5" aria-hidden />
        </span>
        Уточнили: {labels}
      </div>
    )
  }

  return (
    <motion.button
      type="button"
      onClick={onOpen}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      className="group mt-3 flex w-full items-center gap-3.5 rounded-2xl border border-border bg-card p-3 pr-4 text-left shadow-[0_14px_34px_-26px_rgba(15,23,42,0.5)] transition-colors hover:border-highlight/30"
    >
      <span aria-hidden className="relative h-11 w-11 shrink-0">
        <span className="absolute inset-0 translate-x-1 translate-y-1 rotate-6 rounded-xl border border-border bg-accent" />
        <span className="absolute inset-0 flex items-center justify-center rounded-xl bg-highlight text-[15px] font-semibold text-white">
          {plans.length}
        </span>
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] font-semibold text-foreground">
          {plans.length} {plural(plans.length, ['вопрос', 'вопроса', 'вопросов'])} до подборки
        </span>
        <span className="block truncate text-[13px] text-muted-foreground">{labels}</span>
      </span>
      <span className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors group-hover:bg-primary-hover">
        Ответить
      </span>
    </motion.button>
  )
}
