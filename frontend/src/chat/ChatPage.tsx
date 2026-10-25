import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { AnimatePresence, MotionConfig } from 'motion/react'
import { LogoMark } from '@/components/LogoMark'
import { ScrollRow } from '@/components/ScrollRow'
import { PageHeader, type Crumb } from '@/components/PageHeader'
import { MapIcon } from '@heroicons/react/20/solid'
import { Button } from '@/components/ui/button'
import { EXAMPLE_TRIPS } from '@/lib/exampleTrips'
import type { BriefAnswers, DestinationsCard } from '@/types/api'
import { ClarifyFlow } from './clarify/ClarifyOverlay'
import { ClarifyPrompt } from './clarify/ClarifyPrompt'
import { AgentTracePanel } from './components/AgentTracePanel'
import { MessagesSkeleton } from './components/ChatSkeletons'
import { Composer } from './components/Composer'
import { DestinationCards } from './components/DestinationCards'
import { FlightLoader } from './components/FlightLoader'
import { MessageContent } from './components/MessageContent'
import { TripPlanPanel } from './components/TripPlanPanel'
import { useChatSession } from './hooks/useChatSession'
import { useResizablePanel } from './hooks/useResizablePanel'
import type { ChatLayoutContext, WorkspaceChatMessage } from './types'

// Long enough for the agent's words to finish typing in the chat before the cards fly in.
const CLARIFY_OPEN_DELAY_MS = 700
const EMPTY_STATE_INTRO =
  'Напишите, куда и как хотите поехать. Агент уточнит главное, подберёт варианты и соберёт план поездки.'

function readHandoffQuery(state: unknown): string | null {
  if (state && typeof state === 'object' && 'query' in state && typeof state.query === 'string') {
    return state.query.trim() || null
  }
  return null
}

interface PlanToggleProps {
  open: boolean
  onToggle: () => void
}

function PlanToggle({ open, onToggle }: PlanToggleProps) {
  return (
    <Button variant="outline" size="sm" onClick={onToggle} aria-pressed={open} className="rounded-lg bg-card">
      <MapIcon className="text-highlight" />
      <span className="whitespace-nowrap">{open ? 'Скрыть план' : 'План поездки'}</span>
    </Button>
  )
}

interface MessageBubbleProps {
  message: WorkspaceChatMessage
  isStreaming: boolean
  /** The latest message: its cards take answers and picks (sent once the chat is idle). */
  isLast: boolean
  busy: boolean
  onOpenClarify: () => void
  onPick: (card: DestinationsCard) => void
}

function MessageBubble({ message, isStreaming, isLast, busy, onOpenClarify, onPick }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-accent px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap wrap-break-word text-foreground">
          {message.content}
        </div>
      </div>
    )
  }
  const { widget, content } = message
  const working = isStreaming && !widget && (!content || message.phase === 'working')
  return (
    <div className="min-w-0">
      {!working && <AgentTracePanel steps={message.traceSteps ?? []} isStreaming={false} />}
      {content && <MessageContent text={content} />}
      <AnimatePresence>
        {working && (
          <div key="loader" className={content ? 'mt-3' : undefined}>
            <FlightLoader steps={message.traceSteps ?? []} />
          </div>
        )}
      </AnimatePresence>
      {widget?.type === 'clarify' && <ClarifyPrompt widget={widget} pending={isLast} onOpen={onOpenClarify} />}
      {widget?.type === 'destinations' && (
        <DestinationCards widget={widget} canPick={isLast && !busy} onPick={onPick} />
      )}
    </div>
  )
}

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const { planPanelOpen, setPlanPanelOpen } = useOutletContext<ChatLayoutContext>()
  const { messages, send, isLoading, error, streamingId, chatTitle, chatLoading } = useChatSession(chatId)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const lastMessageRef = useRef<HTMLDivElement>(null)
  const busy = isLoading || chatLoading
  const panel = useResizablePanel({ storageKey: 'chat.planPanelWidth', min: 300, max: 560, initial: 380 })
  const last = messages.at(-1)
  const lastWidget = last?.widget
  const pendingClarify = last && lastWidget?.type === 'clarify' && streamingId !== last.id ? lastWidget : null
  const pendingId = pendingClarify ? last!.id : null
  const [clarifyOpenFor, setClarifyOpenFor] = useState<string | null>(null)
  const autoOpened = useRef<string | null>(null)

  useEffect(() => {
    if (!pendingId || busy || autoOpened.current === pendingId) return
    // marked inside the timer, so StrictMode's double effect cannot cancel the only opening
    const timer = setTimeout(() => {
      autoOpened.current = pendingId
      setClarifyOpenFor(pendingId)
    }, CLARIFY_OPEN_DELAY_MS)
    return () => clearTimeout(timer)
  }, [pendingId, busy])

  useEffect(() => {
    // Cards are taller than the screen: show them from the top, starting with the agent's words.
    if (lastWidget) lastMessageRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    else messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, lastWidget])

  useEffect(() => {
    const query = readHandoffQuery(location.state)
    if (!query) return
    // Deferred so StrictMode's mount-unmount-mount does not abort the run it just started.
    const timer = setTimeout(() => {
      navigate(location.pathname, { replace: true, state: null })
      send(query)
    }, 0)
    return () => clearTimeout(timer)
  }, [location.state, location.pathname, navigate, send])

  const submit = (text: string = input) => {
    if (!text.trim() || busy) return
    setInput('')
    send(text)
  }
  const togglePlan = () => setPlanPanelOpen((v) => !v)
  const breadcrumb: Crumb[] = chatLoading
    ? [{ label: 'Чаты', href: '/chat' }, { label: 'Загрузка', pending: true }]
    : messages.length
      ? [{ label: 'Чаты', href: '/chat' }, { label: chatTitle ?? 'Новый чат' }]
      : [{ label: 'Новый чат' }]
  const composer = <Composer value={input} onChange={setInput} onSubmit={() => submit()} disabled={busy} />
  const errorBanner = error && (
    <div
      role="alert"
      className="shrink-0 rounded-xl border border-danger/20 bg-danger-soft px-4 py-2.5 text-[13px] text-danger"
    >
      {error}
    </div>
  )

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-0 min-w-0 flex-1 flex-row overflow-hidden">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <PageHeader breadcrumb={breadcrumb} headerRight={<PlanToggle open={planPanelOpen} onToggle={togglePlan} />} />

          {chatLoading || messages.length > 0 ? (
            <>
              {chatLoading ? (
                <div className="min-h-0 flex-1 overflow-hidden">
                  <MessagesSkeleton />
                </div>
              ) : (
                <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-y-contain">
                  <div className="flex min-h-full flex-col justify-end pt-4 pb-6">
                    <div className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-6 max-md:px-4">
                      {errorBanner}
                      {messages.map((m, i) => (
                        <div key={m.id} ref={i === messages.length - 1 ? lastMessageRef : undefined} className="scroll-mt-4">
                          <MessageBubble
                            message={m}
                            isStreaming={streamingId === m.id}
                            isLast={i === messages.length - 1}
                          busy={busy}
                            onOpenClarify={() => setClarifyOpenFor(m.id)}
                            onPick={(card) => send(card.type === 'route' ? `Выбираю маршрут ${card.name}` : `Выбираю ${card.name}`)}
                          />
                        </div>
                      ))}
                      <div ref={messagesEndRef} />
                    </div>
                  </div>
                </div>
              )}
              <div className="shrink-0 px-6 pt-2 pb-5 max-md:px-4">
                <div className="mx-auto max-w-[720px]">{composer}</div>
              </div>
            </>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-6 pt-6 pb-16 max-md:px-4">
              <div className="flex w-full max-w-[min(92vw,44rem)] flex-col gap-5">
                <div className="flex flex-col items-center gap-3 text-center">
                  <LogoMark className="h-14 w-14" />
                  <h1 className="m-0 text-[clamp(26px,3vw,34px)] font-semibold tracking-tight text-foreground">
                    Куда отправимся?
                  </h1>
                </div>
                {errorBanner}
                <ScrollRow label="Примеры поездок" className="self-stretch max-md:-mx-4">
                  {EXAMPLE_TRIPS.map((trip) => (
                    <button
                      key={trip.label}
                      type="button"
                      onClick={() => submit(trip.query)}
                      disabled={isLoading}
                      title={trip.query}
                      className="min-h-[36px] rounded-full border border-border bg-card px-4 py-1.5 text-sm text-muted-foreground transition-all hover:-translate-y-0.5 hover:border-primary hover:bg-accent hover:text-foreground disabled:opacity-50"
                    >
                      {trip.label}
                    </button>
                  ))}
                </ScrollRow>
                {composer}
                <p className="m-0 text-center text-sm leading-relaxed text-muted-foreground">{EMPTY_STATE_INTRO}</p>
              </div>
            </div>
          )}
        </div>

        {pendingClarify && pendingId && (
        <ClarifyFlow
          key={pendingId}
          widget={pendingClarify}
          intro={last?.content ?? ''}
          open={clarifyOpenFor === pendingId}
          busy={busy}
          onOpenChange={(open) => setClarifyOpenFor(open ? pendingId : null)}
          onSubmit={(text: string, answers: BriefAnswers) => send(text, answers)}
        />
      )}

      {planPanelOpen && (
          <>
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Изменить ширину плана поездки"
              tabIndex={0}
              onMouseDown={panel.startResize}
              onDoubleClick={panel.reset}
              onKeyDown={panel.onSeparatorKeyDown}
              className="hidden w-1.5 shrink-0 cursor-col-resize bg-border select-none hover:bg-faintest focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none active:bg-faint md:block"
            />
            <div
              className={`min-h-0 overflow-hidden max-md:fixed max-md:inset-0 max-md:z-50 md:w-(--plan-w) md:shrink-0 ${panel.isResizing ? '' : 'transition-[width] duration-300 ease-in-out'}`}
              style={{ '--plan-w': `${panel.width}px` } as CSSProperties}
            >
              <TripPlanPanel onClose={() => setPlanPanelOpen(false)} />
            </div>
          </>
        )}
      </div>
    </MotionConfig>
  )
}
