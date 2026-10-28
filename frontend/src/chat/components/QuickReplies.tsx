import { motion } from 'motion/react'
import { ArrowTurnDownRightIcon, ClockIcon } from '@heroicons/react/20/solid'
import type { MemoryNudge } from '@/types/api'

interface QuickRepliesProps {
  replies: string[]
  onPick: (text: string) => void
  /** From the traveller's earlier trips, once per trip: it goes first and says where it comes from. */
  nudge?: MemoryNudge | null
}

/** A few next steps under the latest answer: one tap sends it. They come in after the cards and leave once
 * one is used, since the next answer brings its own. */
export function QuickReplies({ replies, onPick, nudge }: QuickRepliesProps) {
  if (!replies.length) return null
  return (
    <motion.ul
      aria-label="Быстрые ответы"
      className="m-0 mt-4 flex list-none flex-wrap gap-2 p-0"
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.06, delayChildren: 0.5 } } }}
    >
      {nudge && (
        <motion.li
          variants={{
            hidden: { opacity: 0, x: -8, scale: 0.94 },
            show: { opacity: 1, x: 0, scale: 1, transition: { type: 'spring', stiffness: 420, damping: 26 } },
          }}
          className="list-none"
        >
          <button
            type="button"
            onClick={() => onPick(nudge.text)}
            title={`Помню из поездки «${nudge.source}»`}
            className="group inline-flex min-h-9 items-center gap-1.5 rounded-full border border-primary bg-accent px-3.5 py-1.5 text-[13px] font-medium text-foreground shadow-[0_6px_16px_-14px_rgba(15,23,42,0.5)] transition-[transform,background-color] duration-200 hover:-translate-y-0.5 hover:bg-primary/40 active:translate-y-0"
          >
            <ClockIcon aria-hidden className="h-3.5 w-3.5 text-[#3f7d22]" />
            {nudge.text}
          </button>
        </motion.li>
      )}
      {replies.map((text) => (
        <motion.li
          key={text}
          variants={{
            hidden: { opacity: 0, x: -8, scale: 0.94 },
            show: { opacity: 1, x: 0, scale: 1, transition: { type: 'spring', stiffness: 420, damping: 26 } },
          }}
          className="list-none"
        >
          <button
            type="button"
            onClick={() => onPick(text)}
            className="group inline-flex min-h-9 items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-1.5 text-[13px] font-medium text-foreground shadow-[0_6px_16px_-14px_rgba(15,23,42,0.5)] transition-[transform,border-color,background-color] duration-200 hover:-translate-y-0.5 hover:border-primary hover:bg-accent active:translate-y-0"
          >
            <ArrowTurnDownRightIcon aria-hidden className="h-3.5 w-3.5 text-faint transition-colors group-hover:text-[#3f7d22]" />
            {text}
          </button>
        </motion.li>
      ))}
    </motion.ul>
  )
}
