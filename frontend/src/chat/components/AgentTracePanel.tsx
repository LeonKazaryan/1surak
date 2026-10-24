import { useState } from 'react'
import { CheckIcon } from '@heroicons/react/16/solid'
import { ChevronRightIcon, ExclamationCircleIcon } from '@heroicons/react/20/solid'
import { LogoMark } from '@/components/LogoMark'
import type { ChatTraceStep } from '../types'

interface AgentTracePanelProps {
  steps: ChatTraceStep[]
  isStreaming: boolean
}

function StepIcon({ step }: { step: ChatTraceStep }) {
  if (step.kind === 'error') {
    return <ExclamationCircleIcon className="mt-[3px] h-3.5 w-3.5 shrink-0 text-danger" aria-hidden />
  }
  if (step.status === 'done') {
    return (
      <span className="mt-[3px] flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <CheckIcon className="h-2.5 w-2.5" aria-hidden />
      </span>
    )
  }
  return (
    <span className="mt-[3px] flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-secondary">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-highlight" />
    </span>
  )
}

function StepRow({ step }: { step: ChatTraceStep }) {
  if (step.kind !== 'tool') {
    return (
      <li className="flex items-start gap-2">
        <StepIcon step={step} />
        <p className={`m-0 text-xs leading-relaxed ${step.kind === 'error' ? 'text-danger' : 'text-muted-foreground'}`}>
          {step.detail}
        </p>
      </li>
    )
  }
  const hasArgs = Boolean(step.args && Object.keys(step.args).length)
  return (
    <li className="flex items-start gap-2">
      <StepIcon step={step} />
      <div className="min-w-0 flex-1">
        <p className="m-0 text-[13px] leading-snug text-foreground">{step.title}</p>
        {step.status === 'done' && step.resultLine && (
          <p className="m-0 mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.resultLine}</p>
        )}
        {hasArgs && (
          <details className="mt-1">
            <summary className="list-none text-[11px] text-faint transition-colors select-none hover:text-foreground [&::-webkit-details-marker]:hidden">
              детали
            </summary>
            <pre className="m-0 mt-1 max-h-36 overflow-auto rounded-md bg-secondary p-2 text-[10px] whitespace-pre-wrap wrap-break-word text-secondary-foreground">
              {JSON.stringify(step.args, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </li>
  )
}

/** Live "what the agent is doing" block: open while streaming, collapsible afterwards. */
export function AgentTracePanel({ steps, isStreaming }: AgentTracePanelProps) {
  const [openAfterDone, setOpenAfterDone] = useState(false)
  if (!steps.length) return null

  const tools = steps.filter((s) => s.kind === 'tool')
  const running = tools.findLast((t) => t.status === 'running')
  const title = running?.title ?? tools.at(-1)?.title ?? 'Что делаю сейчас'
  const doneCount = tools.filter((t) => t.status === 'done').length
  const summary = isStreaming || !tools.length ? title : `${title} · ${doneCount}/${tools.length}`

  return (
    <details
      className="group/trace mb-3"
      open={isStreaming || openAfterDone}
      onToggle={(e) => {
        if (!isStreaming) setOpenAfterDone(e.currentTarget.open)
      }}
    >
      <summary className="-mx-2 flex list-none items-center gap-2 rounded-lg px-2 py-1 transition-colors select-none hover:bg-secondary [&::-webkit-details-marker]:hidden">
        <LogoMark className={`h-7 w-7 shrink-0 ${isStreaming ? 'animate-logo-pulse' : ''}`} />
        <ChevronRightIcon
          className="h-4 w-4 text-faint transition-transform duration-200 group-open/trace:rotate-90"
          aria-hidden
        />
        <span className={`min-w-0 flex-1 truncate text-[13px] text-muted-foreground ${isStreaming ? 'animate-breathe' : ''}`}>
          {summary}
        </span>
        {isStreaming ? (
          <span className="flex shrink-0 items-center gap-1" aria-hidden>
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-faintest [animation-delay:0ms]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-faintest [animation-delay:120ms]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-faintest [animation-delay:240ms]" />
          </span>
        ) : (
          <span className="shrink-0 text-[11px] text-faint">
            <span className="group-open/trace:hidden">развернуть</span>
            <span className="hidden group-open/trace:inline">свернуть</span>
          </span>
        )}
      </summary>
      <ol className="mt-2 ml-0 flex list-none flex-col gap-2 border-l-2 border-primary/60 pb-1 pl-4">
        {steps.map((step) => (
          <StepRow key={step.id} step={step} />
        ))}
      </ol>
    </details>
  )
}
