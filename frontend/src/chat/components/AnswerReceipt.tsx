import type { ComponentType, SVGProps } from 'react'
import { motion } from 'motion/react'
import {
  CalendarDaysIcon,
  CheckBadgeIcon,
  MapIcon,
  PaperAirplaneIcon,
  SparklesIcon,
  UserGroupIcon,
  WalletIcon,
} from '@heroicons/react/20/solid'

type Icon = ComponentType<SVGProps<SVGSVGElement>>

// the answers are written by describeAnswers (widgets.ts): its own words tell which card each one came from
const ICONS: [RegExp, Icon][] = [
  [/вылет/i, PaperAirplaneIcon],
  [/бюджет/i, WalletIcon],
  [/виз/i, CheckBadgeIcon],
  [/город/i, MapIcon],
  [/взросл|дет|ребён|один\b|вдвоём/i, UserGroupIcon],
  [/ноч|январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр/i, CalendarDaysIcon],
]

function iconFor(part: string): Icon {
  return ICONS.find(([re]) => re.test(part))?.[1] ?? SparklesIcon
}

/** The answers given on the question cards, shown as a receipt rather than a chat bubble: they filled in
 * the trip, and the header above took them in. */
export function AnswerReceipt({ text }: { text: string }) {
  const parts = text.split(' · ').map((p) => p.trim()).filter(Boolean)
  return (
    <div className="flex justify-end">
      <motion.div
        initial={{ opacity: 0, scale: 0.9, rotate: -1.5, y: 10 }}
        animate={{ opacity: 1, scale: 1, rotate: 0, y: 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 22 }}
        className="max-w-[85%] origin-bottom-right rounded-[20px] rounded-br-md border border-primary/60 bg-card p-3 shadow-[0_14px_34px_-24px_rgba(15,23,42,0.45)]"
      >
        <p className="m-0 mb-2 flex items-center gap-1.5 text-[12px] font-semibold text-[#3f7d22]">
          <span className="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-primary">
            <svg viewBox="0 0 16 16" className="h-3 w-3" aria-hidden>
              <motion.path
                d="M3.5 8.5 6.5 11.5 12.5 4.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-foreground"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.45, delay: 0.25, ease: 'easeOut' }}
              />
            </svg>
          </span>
          Ответил на вопросы
        </p>
        <ul className="m-0 flex list-none flex-wrap justify-end gap-1.5 p-0" aria-label="Ответы">
          {parts.map((part, i) => {
            const Icon = iconFor(part)
            return (
              <motion.li
                key={part}
                initial={{ opacity: 0, y: 6, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ type: 'spring', stiffness: 420, damping: 24, delay: 0.15 + i * 0.06 }}
                className="inline-flex items-center gap-1.5 rounded-full bg-accent px-2.5 py-1 text-[13px] font-medium text-foreground"
              >
                <Icon aria-hidden className="h-3.5 w-3.5 shrink-0 text-[#3f7d22]" />
                <span className="first-letter:uppercase">{part}</span>
              </motion.li>
            )
          })}
        </ul>
      </motion.div>
    </div>
  )
}
