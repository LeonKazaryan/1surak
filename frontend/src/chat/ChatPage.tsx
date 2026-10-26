import { useCallback, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { ArrowPathIcon } from '@heroicons/react/20/solid'
import { LogoMark } from '@/components/LogoMark'
import { ScrollRow } from '@/components/ScrollRow'
import { PageHeader, type Crumb } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { useSidebar } from '@/components/ui/sidebar'
import { useIsMobile } from '@/hooks/use-mobile'
import { EXAMPLE_TRIPS } from '@/lib/exampleTrips'
import type { BookingEvent, BriefAnswers, Currency, DestinationsCard } from '@/types/api'
import { ClarifyFlow } from './clarify/ClarifyOverlay'
import { ClarifyPrompt } from './clarify/ClarifyPrompt'
import { AgentTracePanel } from './components/AgentTracePanel'
import { MessagesSkeleton } from './components/ChatSkeletons'
import { Composer } from './components/Composer'
import { DestinationCards } from './components/DestinationCards'
import { FlightLoader } from './components/FlightLoader'
import { MessageContent } from './components/MessageContent'
import { DetailsPanel } from './components/DetailsPanel'
import { PlaceDetails } from './components/PlaceDetails'
import { RouteDetails } from './components/RouteDetails'
import { TripFreshness } from './components/TripFreshness'
import { useChatSession } from './hooks/useChatSession'
import { BookingCard } from './plan/BookingCard'
import { FlightPlanCards } from './components/FlightPlanCard'
import type { BookFn } from './plan/CheckoutSheet'
import { TripPlan } from './plan/TripPlan'
import { isFailed } from './trace'
import type { WorkspaceChatMessage } from './types'

// Long enough for the agent's words to finish typing in the chat before the cards fly in.
const CLARIFY_OPEN_DELAY_MS = 700
const NEW_DATES_PROMPT = 'Перенеси поездку на '
const CHANGE_PROMPT = 'Хотите что-то изменить?'
const EMPTY_STATE_INTRO =
  'Напишите, куда и как хотите поехать. Агент уточнит главное, подберёт варианты и соберёт план поездки.'
const DETAILS_WIDTH = 380
// the --ease-glide curve from index.css, so the panel moves like the sidebar
const DETAILS_TRANSITION = { duration: 0.3, ease: [0.215, 0.61, 0.355, 1] } as const
const DETAILS_WIDEN = { initial: { width: 0 }, animate: { width: DETAILS_WIDTH }, exit: { width: 0 } }
const DETAILS_SLIDE = { initial: { x: '100%' }, animate: { x: 0 }, exit: { x: '100%' } }

interface OpenDetails {
  chatId?: string
  card: DestinationsCard
  currency: Currency
}

function readHandoffQuery(state: unknown): string | null {
  if (state && typeof state === 'object' && 'query' in state && typeof state.query === 'string') {
    return state.query.trim() || null
  }
  return null
}

interface MessageBubbleProps {
  message: WorkspaceChatMessage
  isStreaming: boolean
  /** The latest message: its cards take answers and picks (sent once the chat is idle). */
  isLast: boolean
  busy: boolean
  onOpenClarify: () => void
  onPick: (card: DestinationsCard) => void
  detailsId: string | null
  onDetails: (card: DestinationsCard, currency: Currency) => void
  /** The trip's latest plan: it can still be booked or changed. */
  latestPlan: boolean
  booking?: BookingEvent
  onAsk: (text: string) => void
  onBook: BookFn
  onRetry: () => void
}

function MessageBubble(props: MessageBubbleProps) {
  const { message, isStreaming, isLast, busy, onOpenClarify, onPick, detailsId, onDetails } = props
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
      {isLast && !busy && isFailed(message) && (
        <Button variant="outline" size="sm" onClick={props.onRetry} className="mt-3 rounded-full bg-card">
          <ArrowPathIcon aria-hidden />
          Повторить
        </Button>
      )}
      <AnimatePresence>
        {working && (
          <div key="loader" className={content ? 'mt-3' : undefined}>
            <FlightLoader steps={message.traceSteps ?? []} />
          </div>
        )}
      </AnimatePresence>
      {widget?.type === 'clarify' && <ClarifyPrompt widget={widget} pending={isLast} onOpen={onOpenClarify} />}
      {widget?.type === 'destinations' && (
        <DestinationCards widget={widget} canPick={isLast && !busy} onPick={onPick} detailsId={detailsId} onDetails={onDetails} />
      )}
      {widget?.type === 'trip_plan' && (
        <TripPlan plan={widget} canAct={props.latestPlan && !busy} booking={props.booking} onAsk={props.onAsk} onBook={props.onBook} />
      )}
      {widget?.type === 'booking' && <BookingCard booking={widget} />}
      {widget?.type === 'flight_plan' && <FlightPlanCards widget={widget} />}
    </div>
  )
}

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const { messages, send, isLoading, error, streamingId, chatTitle, chatLoading, trip, refresh, refreshing, book, retry } =
    useChatSession(chatId)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const lastMessageRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const busy = isLoading || chatLoading || refreshing
  const hasCards = messages.some(
    (m) => m.widget?.type === 'destinations' || m.widget?.type === 'trip_plan' || m.widget?.type === 'flight_plan',
  )
  // a booking always buys the latest plan before it
  const { latestPlanId, bookings } = useMemo(() => {
    const booked = new Map<string, BookingEvent>()
    let planId: string | null = null
    for (const m of messages) {
      if (m.widget?.type === 'trip_plan') planId = m.id
      else if (m.widget?.type === 'booking' && planId) booked.set(planId, m.widget)
    }
    return { latestPlanId: planId, bookings: booked }
  }, [messages])
  const last = messages.at(-1)
  const lastWidget = last?.widget
  const pendingClarify = last && lastWidget?.type === 'clarify' && streamingId !== last.id ? lastWidget : null
  const pendingId = pendingClarify ? last!.id : null
  const [clarifyOpenFor, setClarifyOpenFor] = useState<string | null>(null)
  const autoOpened = useRef<string | null>(null)
  const isMobile = useIsMobile()
  const { setOpen: setSidebarOpen } = useSidebar()
  const foldSidebar = useEffectEvent(() => setSidebarOpen(false))
  const [details, setDetails] = useState<OpenDetails | null>(null)
  const shownDetails = details?.chatId === chatId ? details : null
  const closeDetails = useCallback(() => setDetails(null), [])
  const toggleDetails = (card: DestinationsCard, currency: Currency) =>
    setDetails((open) => (open && open.chatId === chatId && open.card.id === card.id ? null : { chatId, card, currency }))

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
      foldSidebar()
      send(query)
    }, 0)
    return () => clearTimeout(timer)
  }, [location.state, location.pathname, navigate, send])

  const submit = (text: string = input) => {
    if (!text.trim() || busy) return
    setInput('')
    // a new trip gets the whole screen; the user can bring the sidebar back
    if (!messages.length) setSidebarOpen(false)
    send(text)
  }
  const breadcrumb: Crumb[] = chatLoading
    ? [{ label: 'Поездки', href: '/chat' }, { label: 'Загрузка', pending: true }]
    : messages.length
      ? [{ label: 'Поездки', href: '/chat' }, { label: chatTitle ?? 'Новая поездка' }]
      : [{ label: 'Новая поездка' }]
  const composer = (
    <Composer
      ref={composerRef}
      value={input}
      onChange={setInput}
      onSubmit={() => submit()}
      disabled={busy}
      placeholder={hasCards ? CHANGE_PROMPT : undefined}
    />
  )
  const freshness = trip && hasCards && !isLoading && !chatLoading && (
    <TripFreshness
      status={trip}
      refreshing={refreshing}
      onRefresh={refresh}
      onNewDates={() => {
        setInput(NEW_DATES_PROMPT)
        composerRef.current?.focus()
      }}
    />
  )
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
          <PageHeader breadcrumb={breadcrumb} />

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
                            detailsId={shownDetails?.card.id ?? null}
                            onDetails={toggleDetails}
                            latestPlan={m.id === latestPlanId && !trip?.dates_passed}
                            booking={bookings.get(m.id)}
                            onAsk={submit}
                            onBook={book}
                            onRetry={retry}
                          />
                        </div>
                      ))}
                      <div ref={messagesEndRef} />
                    </div>
                  </div>
                </div>
              )}
              <div className="shrink-0 px-6 pt-2 pb-5 max-md:px-4">
                <div className="mx-auto max-w-[720px]">
                  {freshness}
                  {composer}
                </div>
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
                  <p className="m-0 max-w-md text-[15px] leading-relaxed text-balance text-muted-foreground">{EMPTY_STATE_INTRO}</p>
                </div>
                {errorBanner}
                {composer}
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

        <AnimatePresence initial={false}>
          {shownDetails && (
            <motion.aside
              key="place-details"
              {...(isMobile ? DETAILS_SLIDE : DETAILS_WIDEN)}
              transition={DETAILS_TRANSITION}
              className="min-h-0 shrink-0 overflow-hidden border-border bg-card max-md:fixed max-md:inset-0 max-md:z-50 md:border-l"
            >
              <div className="h-full md:w-[380px]">
                <DetailsPanel key={shownDetails.card.id} title={shownDetails.card.name} currency={shownDetails.currency} onClose={closeDetails}>
                  {shownDetails.card.type === 'route' ? <RouteDetails card={shownDetails.card} /> : <PlaceDetails card={shownDetails.card} />}
                </DetailsPanel>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  )
}
