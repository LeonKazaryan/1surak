import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { bookTrip, fetchChatMessages, fetchChatMeta, refreshChat, sendChatStream } from '@/api/client'
import type { BookingEvent, BriefAnswers, ChatMeta, ChatStreamDone, PlanFix, TripStatus } from '@/types/api'
import { addMyChat } from '@/chat/chatStorage'
import { createTextPump } from '@/chat/textPump'
import { applyTraceEvent, isFailed, rehydrateTrace } from '@/chat/trace'
import { isWidgetEvent, widgetFromTrace } from '@/chat/widgets'
import { departureCityKnown, getDepartureCity, saveDepartureCity } from '@/lib/departureCity'
import { getCurrencyChoice } from '@/lib/currency'
import type { ChatLayoutContext, ChatTraceStep, WorkspaceChatMessage } from '@/chat/types'

const MAX_RECENT_CHATS = 50
const SEND_ERROR = 'Не удалось получить ответ. Проверьте, что сервер запущен, и попробуйте ещё раз.'
const LOAD_ERROR = 'Не удалось загрузить эту поездку.'
const REFRESH_ERROR = 'Не удалось обновить цены. Попробуйте ещё раз чуть позже.'

interface ActiveRun {
  id: string
  chatId: string
  controller: AbortController
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === 'AbortError'
}

function tripStatus(source: Partial<TripStatus>): Partial<TripStatus> {
  const { summary, departure, priced_at, stale, dates_passed } = source
  return { summary, departure, priced_at, stale, dates_passed }
}

function upsertRecent(prev: ChatMeta[], done: ChatStreamDone): ChatMeta[] {
  const existing = prev.find((c) => c.id === done.chat_id)
  const now = new Date().toISOString()
  const entry: ChatMeta = {
    id: done.chat_id,
    title: done.title ?? existing?.title ?? null,
    created_at: existing?.created_at ?? now,
    updated_at: now,
    ...tripStatus(done),
  }
  return [entry, ...prev.filter((c) => c.id !== done.chat_id)].slice(0, MAX_RECENT_CHATS)
}

function toWorkspaceMessage(m: Awaited<ReturnType<typeof fetchChatMessages>>['messages'][number]): WorkspaceChatMessage {
  const trace = Array.isArray(m.trace) ? m.trace : []
  return {
    id: m.id,
    role: m.role,
    content: m.content,
    traceSteps: rehydrateTrace(trace),
    widget: widgetFromTrace(trace),
    timestamp: new Date(m.created_at),
  }
}

/** Loads the chat in the URL and streams new turns into the message list shared by the chat layout. */
export function useChatSession(urlChatId: string | undefined) {
  const navigate = useNavigate()
  const { chatMessages, setMessages, activeChatId, setActiveChatId, setRecentChats } =
    useOutletContext<ChatLayoutContext>()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const [chatTitle, setChatTitle] = useState<string | null>(null)
  const [trip, setTrip] = useState<Partial<TripStatus> | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [chatLoading, setChatLoading] = useState(() => Boolean(urlChatId))
  const activeRun = useRef<ActiveRun | null>(null)
  const openChatId = useRef(urlChatId)

  useEffect(() => {
    openChatId.current = urlChatId
  }, [urlChatId])

  useEffect(() => () => activeRun.current?.controller.abort(), [])

  useEffect(() => {
    if (activeRun.current && activeRun.current.chatId !== (urlChatId ?? null)) {
      activeRun.current.controller.abort()
      activeRun.current = null
      setIsLoading(false)
      setStreamingId(null)
    }
    setError(null)
    if (!urlChatId) {
      setMessages([])
      setActiveChatId(null)
      setChatTitle(null)
      setTrip(null)
      setChatLoading(false)
      return
    }
    if (urlChatId === activeChatId) {
      setChatLoading(false)
      return
    }
    let stale = false
    setChatLoading(true)
    setActiveChatId(urlChatId)
    Promise.all([fetchChatMeta(urlChatId), fetchChatMessages(urlChatId)])
      .then(([meta, data]) => {
        if (stale) return
        setChatTitle(meta.title)
        setTrip(tripStatus(meta))
        setMessages(data.messages.map(toWorkspaceMessage))
      })
      .catch(() => {
        if (stale) return
        setMessages([])
        setError(LOAD_ERROR)
      })
      .finally(() => {
        if (!stale) setChatLoading(false)
      })
    return () => {
      stale = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlChatId])

  const send = useCallback(
    (text: string, answers?: BriefAnswers, retry = false) => {
      const query = text.trim()
      if (!query || isLoading) return

      const assistantId = crypto.randomUUID()
      setMessages((prev) => [
        ...(retry ? prev.slice(0, -2) : prev),
        { id: crypto.randomUUID(), role: 'user', content: query, timestamp: new Date() },
        { id: assistantId, role: 'assistant', content: '', traceSteps: [], phase: 'working', timestamp: new Date() },
      ])
      setStreamingId(assistantId)
      setIsLoading(true)
      setError(null)

      activeRun.current?.controller.abort()
      const run: ActiveRun = {
        id: crypto.randomUUID(),
        chatId: urlChatId ?? crypto.randomUUID(),
        controller: new AbortController(),
      }
      activeRun.current = run
      const isCurrent = () => activeRun.current?.id === run.id
      const patch = (update: Partial<WorkspaceChatMessage>) => {
        if (!isCurrent()) return
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, ...update } : m)))
      }

      let steps: ChatTraceStep[] = []
      let phase: WorkspaceChatMessage['phase'] = 'working'
      const setPhase = (next: WorkspaceChatMessage['phase']) => {
        if (next === phase) return
        phase = next
        patch({ phase })
      }
      const pump = createTextPump((shown) => patch({ content: shown }))

      sendChatStream(
        {
          query,
          chat_id: run.chatId,
          origin: getDepartureCity().name,
          origin_code: getDepartureCity().code,
          origin_known: departureCityKnown(),
          currency: getCurrencyChoice() ?? undefined,
          answers,
          retry,
        },
        (event) => {
          if (!isCurrent()) return
          if (event.type === 'origin') {
            // the user named another city in the message: the next one is sent from it too
            saveDepartureCity({ code: event.code, name: event.name })
            return
          }
          if (event.type === 'assistant_token') {
            pump.push(event.text)
            setPhase('writing')
            return
          }
          if (isWidgetEvent(event)) {
            patch({ widget: event })
            return
          }
          const next = applyTraceEvent(steps, event)
          if (next !== steps) {
            steps = next
            patch({ traceSteps: steps })
            setPhase('working')
          }
        },
        { signal: run.controller.signal },
      )
        .then((done) => {
          if (!isCurrent()) return
          pump.stop()
          patch({ content: done.answer || pump.text(), traceSteps: steps, phase: undefined })
          addMyChat(done.chat_id)
          setActiveChatId(done.chat_id)
          if (done.title) setChatTitle(done.title)
          setTrip(tripStatus(done))
          setRecentChats((prev) => upsertRecent(prev, done))
          if (!urlChatId) navigate(`/chat/${done.chat_id}`, { replace: true })
        })
        .catch((err: unknown) => {
          if (!isCurrent() || isAbortError(err)) return
          pump.stop()
          setError(SEND_ERROR)
          const partial = pump.text()
          if (partial || steps.length) {
            patch({ content: partial, traceSteps: steps, phase: undefined })
          } else {
            setMessages((prev) => prev.filter((m) => m.id !== assistantId))
          }
        })
        .finally(() => {
          if (!isCurrent()) return
          activeRun.current = null
          setIsLoading(false)
          setStreamingId(null)
        })
    },
    [isLoading, navigate, setActiveChatId, setMessages, setRecentChats, urlChatId],
  )

  /** Asks the last question again in place of the reply that failed. */
  const retry = useCallback(() => {
    const [question, reply] = chatMessages.slice(-2)
    if (question?.role !== 'user' || !reply || !isFailed(reply)) return
    send(question.content, undefined, true)
  }, [chatMessages, send])

  const refresh = useCallback(async () => {
    if (!urlChatId || isLoading || refreshing) return
    setRefreshing(true)
    setError(null)
    try {
      const { message, chat } = await refreshChat(urlChatId)
      setRecentChats((prev) => [chat, ...prev.filter((c) => c.id !== chat.id)])
      if (openChatId.current !== urlChatId) return
      setMessages((prev) => [...prev, toWorkspaceMessage(message)])
      setTrip(tripStatus(chat))
    } catch {
      if (openChatId.current === urlChatId) setError(REFRESH_ERROR)
    } finally {
      setRefreshing(false)
    }
  }, [isLoading, refreshing, setMessages, setRecentChats, urlChatId])

  /** Books the trip's latest plan; the booking comes back as a message, added to the chat it was made in. */
  const book = useCallback(
    async (extras: PlanFix['id'][], holder: string): Promise<BookingEvent> => {
      if (!urlChatId) throw new Error('No trip to book')
      const message = await bookTrip(urlChatId, { extras, holder })
      const booking = widgetFromTrace(message.trace)
      if (booking?.type !== 'booking') throw new Error('The booking reply has no booking')
      if (openChatId.current === urlChatId) {
        // a repeat booking returns the message already in the chat, e.g. one booked from another tab
        setMessages((prev) => (prev.some((m) => m.id === message.id) ? prev : [...prev, toWorkspaceMessage(message)]))
      }
      return booking
    },
    [setMessages, urlChatId],
  )

  // The URL changes one render before the load effect runs; without this the old chat flashes.
  const switching = Boolean(urlChatId) && urlChatId !== activeChatId
  return {
    messages: chatMessages,
    send,
    isLoading,
    error,
    streamingId,
    chatTitle,
    chatLoading: chatLoading || switching,
    trip,
    refresh,
    refreshing,
    book,
    retry,
  }
}
