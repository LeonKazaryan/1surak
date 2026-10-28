import { StrictMode } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, type InitialEntry } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatLayout from './ChatLayout'
import ChatPage from './ChatPage'
import * as client from '@/api/client'
import type { BookingEvent, ChatMeta, ChatStreamDone, ChatStreamEvent, TripStatus } from '@/types/api'
import { PLAN } from './plan/testPlan'

vi.mock('@/api/client', () => ({
  sendChatStream: vi.fn(),
  fetchChats: vi.fn().mockResolvedValue({ items: [] }),
  fetchChatMeta: vi.fn(),
  fetchChatMessages: vi.fn(),
  deleteChat: vi.fn().mockResolvedValue(undefined),
  refreshChat: vi.fn(),
  bookTrip: vi.fn(),
  fetchMemory: vi.fn().mockRejectedValue(new Error('offline')),
}))

const sendChatStream = vi.mocked(client.sendChatStream)

function renderChat(entry: InitialEntry = '/chat') {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/chat" element={<ChatLayout />}>
            <Route index element={<ChatPage />} />
            <Route path=":chatId" element={<ChatPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </StrictMode>,
  )
}

function streamReply(events: ChatStreamEvent[], done: ChatStreamDone) {
  sendChatStream.mockImplementation(async (_body, onEvent) => {
    events.forEach(onEvent)
    return done
  })
}

beforeEach(() => {
  localStorage.clear()
  sendChatStream.mockReset()
})

const HURGHADA = {
  id: 'hurghada',
  name: 'Хургада',
  country: 'Египет',
  country_code: 'EG',
  kinds: ['sea' as const],
  visa: 'виза по прибытии',
  visa_easy: true,
  price_level: 1,
  price: 'недорого',
  kids: 'хорошо с детьми',
  kids_fit: 'good' as const,
  climate: null,
  highlights: [],
  watch_out: [],
  why: 'Тёплое море',
}

function savedTrip(status: Partial<ChatMeta>) {
  const meta = { id: 'c1', title: 'Море', created_at: '2026-10-19T12:00:00Z', updated_at: '2026-10-19T12:00:00Z' }
  vi.mocked(client.fetchChatMeta).mockResolvedValue({ ...meta, ...status })
  vi.mocked(client.fetchChatMessages).mockResolvedValue({
    messages: [
      {
        id: 'm1',
        chat_id: 'c1',
        role: 'assistant',
        content: 'Вот что нашёл',
        trace: [{ type: 'destinations', summary: [], cards: [HURGHADA] }],
        created_at: '2026-10-19T12:00:00Z',
      },
    ],
  })
  return meta
}

describe('ChatPage', () => {
  it('should offer to refresh old prices and add the fresh cards', async () => {
    const meta = savedTrip({ stale: true, priced_at: '2026-10-19T12:00:00+00:00' })
    vi.mocked(client.refreshChat).mockResolvedValue({
      message: {
        id: 'm2',
        chat_id: 'c1',
        role: 'assistant',
        content: 'Обновил цены билетов',
        trace: [{ type: 'destinations', summary: [], cards: [{ ...HURGHADA, why: 'Всё ещё тепло' }] }],
        created_at: '2026-10-26T12:00:00Z',
      },
      chat: { ...meta, stale: false, priced_at: '2026-10-26T12:00:00+00:00' },
    })
    renderChat('/chat/c1')

    expect(await screen.findByText('Цены от 19 окт могли измениться')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Обновить цены' }))

    expect(await screen.findByText('Обновил цены билетов')).toBeInTheDocument()
    expect(screen.getByText('Всё ещё тепло')).toBeInTheDocument()
    expect(client.refreshChat).toHaveBeenCalledWith('c1')
    expect(screen.queryByRole('button', { name: 'Обновить цены' })).not.toBeInTheDocument()
  })

  it('should keep a late refresh out of the trip opened since', async () => {
    const meta = savedTrip({ stale: true, priced_at: '2026-10-19T12:00:00+00:00' })
    localStorage.setItem('1surak.myChats', JSON.stringify(['c1', 'c2']))
    vi.mocked(client.fetchChats).mockResolvedValue({ items: [meta, { ...meta, id: 'c2', title: 'Казань' }] })
    let finish!: (value: Awaited<ReturnType<typeof client.refreshChat>>) => void
    vi.mocked(client.refreshChat).mockReturnValue(new Promise((r) => (finish = r)))
    renderChat('/chat/c1')

    await userEvent.click(await screen.findByRole('button', { name: 'Обновить цены' }))
    vi.mocked(client.fetchChatMeta).mockResolvedValue({ ...meta, id: 'c2', title: 'Казань' })
    vi.mocked(client.fetchChatMessages).mockResolvedValue({ messages: [] })
    await userEvent.click(await within(screen.getByTestId('chat-sidebar')).findByRole('link', { name: /Казань/ }))
    finish({
      message: { id: 'm2', chat_id: 'c1', role: 'assistant', content: 'Обновил цены билетов', trace: [], created_at: '2026-10-26T12:00:00Z' },
      chat: { ...meta, stale: false },
    })

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Куда отправимся?' })).toBeInTheDocument())
    expect(screen.queryByText('Обновил цены билетов')).toBeNull()
    vi.mocked(client.fetchChats).mockResolvedValue({ items: [] })
  })

  it('should say when the trip dates have passed and help pick new ones', async () => {
    savedTrip({ stale: true, dates_passed: true, priced_at: '2026-10-19T12:00:00+00:00' })
    renderChat('/chat/c1')

    expect(await screen.findByText('Даты поездки уже прошли')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Выбрать новые даты' }))

    expect(screen.getByRole('textbox', { name: 'Сообщение агенту' })).toHaveValue('Перенеси поездку на ')
  })

  it('should invite changes once destinations are suggested', async () => {
    savedTrip({ stale: false, priced_at: '2026-10-25T12:00:00+00:00' })
    renderChat('/chat/c1')

    expect(await screen.findByText('Вот что нашёл')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Сообщение агенту' })).toHaveAttribute('placeholder', 'Хотите что-то изменить?')
  })

  it('should ask to describe the trip in a new chat', () => {
    renderChat()

    expect(screen.getByRole('textbox', { name: 'Сообщение агенту' })).toHaveAttribute('placeholder', 'Опишите поездку своими словами…')
  })

  it('should not offer a refresh while the prices are fresh', async () => {
    savedTrip({ stale: false, priced_at: '2026-10-25T12:00:00+00:00' })
    renderChat('/chat/c1')

    expect(await screen.findByText('Вот что нашёл')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Обновить цены' })).not.toBeInTheDocument()
  })

  it('should send the trip description handed over from the landing page exactly once', async () => {
    streamReply([{ type: 'assistant_token', text: 'Предлагаю Казань' }], {
      type: 'done',
      answer: 'Предлагаю Казань',
      chat_id: 'chat-1',
      title: 'Казань',
    })
    renderChat({ pathname: '/chat', state: { query: 'Казань на выходные' } })

    expect(await screen.findByText('Предлагаю Казань')).toBeInTheDocument()
    expect(screen.getByText('Казань на выходные')).toBeInTheDocument()
    const breadcrumb = screen.getByRole('navigation', { name: 'breadcrumb' })
    expect(await within(breadcrumb).findByText('Казань')).toBeInTheDocument()
    await waitFor(() => expect(sendChatStream).toHaveBeenCalledTimes(1))
    expect(sendChatStream).toHaveBeenCalledWith(
      expect.objectContaining({ query: 'Казань на выходные' }),
      expect.any(Function),
      expect.anything(),
    )
  })

  it('should send the chosen departure city with the request', async () => {
    localStorage.setItem('1surak.departureCity', JSON.stringify({ code: 'KZN', name: 'Казань' }))
    streamReply([], { type: 'done', answer: 'Ок', chat_id: 'chat-1', title: 'Море' })
    renderChat({ pathname: '/chat', state: { query: 'Хочу к морю' } })

    await waitFor(() =>
      expect(sendChatStream).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'Хочу к морю', origin: 'Казань', origin_code: 'KZN' }),
        expect.any(Function),
        expect.anything(),
      ),
    )
  })

  it('should keep the country of a departure city named in the chat, so prices follow its currency', async () => {
    streamReply([{ type: 'origin', code: 'NQZ', name: 'Астана', country: 'Казахстан' }], {
      type: 'done',
      answer: 'Ок',
      chat_id: 'chat-1',
      title: 'Море',
    })
    renderChat({ pathname: '/chat', state: { query: 'Из Астаны к морю' } })

    await waitFor(() =>
      expect(JSON.parse(localStorage.getItem('1surak.departureCity')!)).toEqual({ code: 'NQZ', name: 'Астана', country: 'Казахстан' }),
    )
  })

  it('should fall back to example trips in the empty state when memory does not answer', async () => {
    renderChat()

    expect(await screen.findByRole('button', { name: 'Тёплое море в ноябре' })).toBeInTheDocument()
  })

  it('should send the typed message and render the streamed answer and tool steps', async () => {
    streamReply(
      [
        { type: 'tool_start', name: 'search', title: 'Ищу направления' },
        { type: 'tool_end', name: 'search', output_preview: 'Нашёл 3 направления' },
        { type: 'assistant_token', text: 'Предлагаю **Хургаду**' },
      ],
      { type: 'done', answer: 'Предлагаю **Хургаду**', chat_id: 'chat-1', title: 'Море в ноябре' },
    )
    renderChat()

    await userEvent.type(screen.getByRole('textbox'), 'Море в ноябре{Enter}')

    expect(await screen.findByText('Хургаду')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('status', { name: 'Агент работает' })).not.toBeInTheDocument())
    expect(screen.getByText('Ищу направления')).toBeInTheDocument()
    expect(sendChatStream).toHaveBeenCalledWith(
      expect.objectContaining({ query: 'Море в ноябре' }),
      expect.any(Function),
      expect.anything(),
    )
  })

  it('should add the finished chat to the recent list in the sidebar', async () => {
    streamReply([], { type: 'done', answer: 'Ок', chat_id: 'chat-1', title: 'Казань на выходные' })
    renderChat()

    await userEvent.type(screen.getByRole('textbox'), 'Казань{Enter}')

    const sidebar = screen.getByTestId('chat-sidebar')
    expect(await within(sidebar).findByText('Казань на выходные')).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('1surak.myChats') ?? '[]')).toEqual(['chat-1'])
  })

  it('should fold the sidebar away once a new chat starts and let the user open it again', async () => {
    document.cookie = 'sidebar_state=; path=/; max-age=0'
    streamReply([], { type: 'done', answer: 'Ок', chat_id: 'chat-1', title: 'Казань' })
    renderChat()
    const sidebar = () => document.querySelector('[data-slot="sidebar"]')
    expect(sidebar()).toHaveAttribute('data-state', 'expanded')

    await userEvent.type(screen.getByRole('textbox'), 'Казань{Enter}')

    await waitFor(() => expect(sidebar()).toHaveAttribute('data-state', 'collapsed'))
    await userEvent.click(screen.getByRole('button', { name: 'Меню' }))
    expect(sidebar()).toHaveAttribute('data-state', 'expanded')
    document.cookie = 'sidebar_state=; path=/; max-age=0'
  })

  it('should show an error banner when the request fails', async () => {
    sendChatStream.mockRejectedValue(new Error('500 Server Error'))
    renderChat()

    await userEvent.type(screen.getByRole('textbox'), 'Привет{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось получить ответ')
  })

  it('should show placeholders for the title and messages while a saved chat loads', async () => {
    let resolveMessages!: (value: Awaited<ReturnType<typeof client.fetchChatMessages>>) => void
    vi.mocked(client.fetchChatMeta).mockResolvedValue({
      id: 'c1',
      title: 'Море в ноябре',
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    })
    vi.mocked(client.fetchChatMessages).mockReturnValue(new Promise((r) => (resolveMessages = r)))
    renderChat('/chat/c1')

    expect(await screen.findByTestId('messages-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('title-skeleton')).toBeInTheDocument()
    resolveMessages({
      messages: [
        { id: 'm1', chat_id: 'c1', role: 'user', content: 'Хочу к морю', trace: [], created_at: '2026-10-24T10:00:00Z' },
      ],
    })
    expect(await screen.findByText('Хочу к морю')).toBeInTheDocument()
    expect(screen.queryByTestId('messages-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByTestId('title-skeleton')).not.toBeInTheDocument()
  })

  it('should load a saved chat from the URL with its agent steps', async () => {
    vi.mocked(client.fetchChatMeta).mockResolvedValue({
      id: 'c1',
      title: 'Море в ноябре',
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    })
    vi.mocked(client.fetchChatMessages).mockResolvedValue({
      messages: [
        { id: 'm1', chat_id: 'c1', role: 'user', content: 'Хочу к морю', trace: [], created_at: '2026-10-24T10:00:00Z' },
        {
          id: 'm2',
          chat_id: 'c1',
          role: 'assistant',
          content: 'Вот варианты',
          trace: [
            { type: 'tool_start', name: 'search', title: 'Ищу направления' },
            { type: 'tool_end', name: 'search', output_preview: 'ok' },
          ],
          created_at: '2026-10-24T10:00:01Z',
        },
      ],
    })
    renderChat('/chat/c1')

    expect(await screen.findByText('Вот варианты')).toBeInTheDocument()
    expect(screen.getByText('Хочу к морю')).toBeInTheDocument()
    expect(screen.getByText('Ищу направления')).toBeInTheDocument()
    expect(screen.getAllByText('Море в ноябре').length).toBeGreaterThan(0)
  })

  it('should not send a message while a saved chat is still loading', async () => {
    vi.mocked(client.fetchChatMeta).mockReturnValue(new Promise(() => {}))
    vi.mocked(client.fetchChatMessages).mockReturnValue(new Promise(() => {}))
    renderChat('/chat/c1')

    await userEvent.type(await screen.findByRole('textbox', { name: 'Сообщение агенту' }), 'Хочу к морю{Enter}')

    expect(sendChatStream).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Отправить' })).toBeDisabled()
  })

  it('should show placeholders instead of the previous chat while switching chats', async () => {
    const meta = (id: string, title: string) => ({
      id,
      title,
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    })
    localStorage.setItem('1surak.myChats', JSON.stringify(['b']))
    vi.mocked(client.fetchChats).mockResolvedValue({ items: [meta('b', 'Казань')] })
    vi.mocked(client.fetchChatMeta).mockImplementation(async (id) => (id === 'a' ? meta('a', 'Море') : meta('b', 'Казань')))
    vi.mocked(client.fetchChatMessages).mockImplementation((id) =>
      id === 'a'
        ? Promise.resolve({
            messages: [
              { id: 'a-m', chat_id: 'a', role: 'assistant' as const, content: 'Ответ про море', trace: [], created_at: '2026-10-24T10:00:00Z' },
            ],
          })
        : new Promise(() => {}),
    )
    renderChat('/chat/a')
    expect(await screen.findByText('Ответ про море')).toBeInTheDocument()

    await userEvent.click(within(screen.getByTestId('chat-sidebar')).getByRole('link', { name: 'Казань' }))

    expect(await screen.findByTestId('messages-skeleton')).toBeInTheDocument()
    expect(screen.queryByText('Ответ про море')).toBeNull()
  })

  it('should keep the chat opened last when an earlier chat finishes loading late', async () => {
    const meta = (id: string, title: string) => ({
      id,
      title,
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    })
    const message = (chatId: string, content: string) => ({
      messages: [{ id: `${chatId}-m`, chat_id: chatId, role: 'assistant' as const, content, trace: [], created_at: '2026-10-24T10:00:00Z' }],
    })
    let finishSlowChat = () => {}
    const slowChat = new Promise<void>((resolve) => {
      finishSlowChat = resolve
    })
    localStorage.setItem('1surak.myChats', JSON.stringify(['b']))
    vi.mocked(client.fetchChats).mockResolvedValue({ items: [meta('b', 'Казань')] })
    vi.mocked(client.fetchChatMeta).mockImplementation(async (id) =>
      id === 'a' ? slowChat.then(() => meta('a', 'Море')) : meta('b', 'Казань'),
    )
    vi.mocked(client.fetchChatMessages).mockImplementation(async (id) =>
      id === 'a' ? slowChat.then(() => message('a', 'Ответ про море')) : message('b', 'Ответ про Казань'),
    )
    renderChat('/chat/a')

    await userEvent.click(await within(screen.getByTestId('chat-sidebar')).findByRole('link', { name: 'Казань' }))
    expect(await screen.findByText('Ответ про Казань')).toBeInTheDocument()
    finishSlowChat()

    await waitFor(() => expect(client.fetchChatMessages).toHaveBeenCalledWith('a'))
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.queryByText('Ответ про море')).toBeNull()
    expect(screen.getByText('Ответ про Казань')).toBeInTheDocument()
  })

  it('should show an error when a saved chat cannot be loaded', async () => {
    vi.mocked(client.fetchChatMeta).mockRejectedValue(new Error('404 Not Found'))
    vi.mocked(client.fetchChatMessages).mockRejectedValue(new Error('404 Not Found'))
    renderChat('/chat/missing')

    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить')
  })

  it('should put the intro under the heading and the trip ideas under the composer', () => {
    renderChat()

    const heading = screen.getByRole('heading', { level: 1, name: 'Куда отправимся?' })
    const intro = screen.getByText(/Напишите, куда и как хотите поехать/)
    const composer = screen.getByRole('textbox', { name: 'Сообщение агенту' })
    const examples = screen.getByRole('group', { name: 'Идеи для поездки' })
    const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)
    expect(follows(heading, intro) && follows(intro, composer) && follows(composer, examples)).toBe(true)
  })

  it('should not offer an empty trip plan panel', () => {
    renderChat()

    expect(screen.queryByRole('button', { name: /План поездки/ })).toBeNull()
    expect(screen.queryByRole('region', { name: 'План поездки' })).toBeNull()
  })

  it('should show the flight loader with the current step while the agent works', async () => {
    sendChatStream.mockImplementation(async (_body, onEvent) => {
      onEvent({ type: 'tool_start', name: 'search_destinations', title: 'Подбираю направления' })
      return new Promise(() => {})
    })
    renderChat()

    await userEvent.type(screen.getByRole('textbox'), 'Море в ноябре{Enter}')

    const loader = await screen.findByRole('status', { name: 'Агент работает' })
    expect(within(loader).getByText('Подбираю направления')).toBeInTheDocument()
    expect(within(loader).getByText('Сверяю климат по месяцам…')).toBeInTheDocument()
  })

  it('should show the rabbit beside the thinking text while the agent works, not only once it is done', async () => {
    sendChatStream.mockImplementation(async () => new Promise(() => {}))
    renderChat()

    await userEvent.type(screen.getByRole('textbox'), 'Море в ноябре{Enter}')

    const loader = await screen.findByRole('status', { name: 'Агент работает' })
    const title = within(loader).getByText('Разбираю запрос')
    expect(title.parentElement?.querySelector('img[src="/logo.png"]')).not.toBeNull()
  })

  it('should move to the next card on a single tap and send the answers in one message', async () => {
    streamReply(
      [
        { type: 'tool_start', name: 'update_trip_brief', title: 'Разбираю запрос' },
        { type: 'tool_end', name: 'update_trip_brief', output_preview: 'Понял' },
        { type: 'assistant_token', text: 'Уточню пару моментов' },
        {
          type: 'clarify',
          questions: [
            { slot: 'travelers', title: 'Кто едет?', hint: null },
            { slot: 'budget', title: 'Какой бюджет?', hint: 'Вы написали «недорого»' },
          ],
          prefill: { kinds: ['sea'], month: 11, nights: null, adults: null, children: 1, children_ages: [], budget_level: null, multi_city: null },
        },
      ],
      { type: 'done', answer: 'Уточню пару моментов', chat_id: 'chat-1', title: 'Море' },
    )
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'К морю с ребёнком, недорого{Enter}')

    const dialog = await screen.findByRole('dialog', { name: 'Уточняющие вопросы' }, { timeout: 3000 })
    expect(within(dialog).getByText('Кто едет?')).toBeInTheDocument()
    expect(within(dialog).getByText('1 ребёнок')).toBeInTheDocument() // what is known is shown, not asked
    expect(within(dialog).queryByRole('button', { name: /Дальше/ })).toBeNull() // no extra buttons
    await userEvent.click(within(dialog).getByRole('button', { name: 'Вдвоём с детьми' }))
    expect(await within(dialog).findByText('Сколько лет ребёнку?')).toBeInTheDocument()

    // closing keeps the picks and the place: the chip in the chat brings back the same card
    await userEvent.click(within(dialog).getByRole('button', { name: 'Закрыть вопросы' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: /2 вопроса до подборки/ }))
    const reopened = await screen.findByRole('dialog', { name: 'Уточняющие вопросы' })
    expect(within(reopened).getByText('Сколько лет ребёнку?')).toBeInTheDocument()

    await userEvent.click(within(reopened).getByRole('button', { name: '5 лет' }))
    expect(await within(reopened).findByText('Вы написали «недорого»')).toBeInTheDocument()
    streamReply([], { type: 'done', answer: 'Ищу', chat_id: 'chat-1', title: 'Море' })
    await userEvent.click(within(reopened).getByRole('button', { name: /Средне/ }))

    await waitFor(() => expect(sendChatStream).toHaveBeenCalledTimes(2), { timeout: 5000 })
    expect(sendChatStream).toHaveBeenLastCalledWith(
      expect.objectContaining({
        query: '2 взрослых + 1 ребёнок (5 лет) · бюджет: средне',
        answers: { adults: 2, children: 1, children_ages: [5], budget_level: 2 },
      }),
      expect.any(Function),
      expect.anything(),
    )
    expect(await screen.findByText('Уточнили: кто едет, бюджет')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('should offer what an earlier trip answered on its card and take it only on a tap', async () => {
    localStorage.setItem('1surak.myChats', JSON.stringify(['old-trip']))
    localStorage.setItem('1surak.forgotten', JSON.stringify(['budget']))
    streamReply(
      [
        { type: 'assistant_token', text: 'Уточню' },
        {
          type: 'clarify',
          questions: [
            { slot: 'travelers', title: 'Кто едет?', hint: null },
            { slot: 'visa', title: 'Учитывать визы?', hint: null },
          ],
          prefill: { kinds: ['sea'], month: 1, nights: [7, 7], adults: null, children: null, children_ages: [], budget_level: null, multi_city: null },
          remembered: { travelers: { adults: 2, children: 1, children_ages: [6], text: 'двое взрослых + ребёнок 6 лет', source: 'Хургада · ноябрь' } },
        },
      ],
      { type: 'done', answer: 'Уточню', chat_id: 'chat-1', title: 'Море' },
    )
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'Хочу на море в январе{Enter}')

    // the earlier trips go with the message, the hidden fact too, so the agent never uses it
    expect(sendChatStream).toHaveBeenCalledWith(
      expect.objectContaining({ history: ['old-trip'], forget: ['budget'] }),
      expect.any(Function),
      expect.anything(),
    )
    const dialog = await screen.findByRole('dialog', { name: 'Уточняющие вопросы' }, { timeout: 3000 })
    const offer = within(dialog).getByRole('button', { name: /Как в прошлый раз: двое взрослых \+ ребёнок 6 лет/ })
    expect(offer).toHaveTextContent('помню из поездки «Хургада · ноябрь»')
    expect(within(dialog).getByRole('button', { name: /Вдвоём/ })).not.toHaveClass('border-primary') // nothing picked for them

    await userEvent.click(offer)
    expect(await within(dialog).findByText('Учитывать визы?', {}, { timeout: 2000 })).toBeInTheDocument() // the ages are not asked
    streamReply([], { type: 'done', answer: 'Ищу', chat_id: 'chat-1', title: 'Море' })
    await userEvent.click(within(dialog).getByRole('button', { name: /Не важно/ }))

    await waitFor(() => expect(sendChatStream).toHaveBeenCalledTimes(2), { timeout: 5000 })
    expect(sendChatStream).toHaveBeenLastCalledWith(
      expect.objectContaining({ answers: { adults: 2, children: 1, children_ages: [6], visa_free_only: false } }),
      expect.any(Function),
      expect.anything(),
    )
  })

  it('should show the plan being put together between the reply and the plan itself', async () => {
    let finish!: () => void
    sendChatStream.mockImplementation(async (_body, onEvent) => {
      onEvent({ type: 'tool_start', name: 'build_trip', title: 'Собираю поездку' })
      onEvent({ type: 'tool_end', name: 'build_trip', output_preview: 'Нячанг' })
      onEvent({ type: 'assistant_token', text: 'Собрал Нячанг на двоих.' })
      onEvent({ type: 'tool_preparing', name: 'show_trip', title: 'Показываю план' })
      await new Promise<void>((resolve) => (finish = resolve))
      return { type: 'done', answer: 'Собрал Нячанг на двоих.', chat_id: 'chat-1', title: 'Нячанг' }
    })
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'Выбираю Нячанг{Enter}')

    const pending = await screen.findByLabelText('Собираю план поездки')
    expect(within(pending).getByRole('status')).toHaveTextContent('Подбираю фотографии')
    expect(within(pending).getByRole('heading')).toHaveTextContent('Ваша поездка')

    finish()
    await waitFor(() => expect(screen.queryByLabelText('Собираю план поездки')).toBeNull())
  })

  it('should put the quick reply from memory first and say where it comes from', async () => {
    streamReply(
      [{ type: 'destinations', summary: [], cards: [HURGHADA] }],
      {
        type: 'done',
        answer: '',
        chat_id: 'chat-1',
        title: 'Море',
        nudge: { text: 'Как в прошлый раз: с видом на море', source: 'Хургада · ноябрь' },
      },
    )
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'Море в ноябре{Enter}')

    const replies = await screen.findByRole('list', { name: 'Быстрые ответы' })
    const first = within(replies).getAllByRole('button')[0]
    expect(first).toHaveTextContent('Как в прошлый раз: с видом на море')
    expect(first).toHaveAttribute('title', 'Помню из поездки «Хургада · ноябрь»')
  })

  it('should open place details in a side panel and close it', async () => {
    streamReply(
      [{ type: 'destinations', summary: [], cards: [{ ...HURGHADA, highlights: ['коралловые рифы'], watch_out: ['ветрено'] }] }],
      { type: 'done', answer: '', chat_id: 'chat-1', title: 'Море' },
    )
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'Море в ноябре{Enter}')

    await userEvent.click(await screen.findByRole('button', { name: 'Подробнее' }))
    const panel = await screen.findByRole('region', { name: 'Хургада, подробнее' })
    expect(within(panel).getByText('коралловые рифы')).toBeInTheDocument()

    await userEvent.click(within(panel).getByRole('button', { name: 'Закрыть' }))
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Хургада, подробнее' })).toBeNull())
  })

  it('should show destination cards and send the picked one', async () => {
    const card = (id: string, name: string) => ({
      id,
      name,
      country: 'Египет',
      country_code: 'EG',
      kinds: ['sea' as const],
      flight_hours: 4.5,
      direct: true,
      visa: 'виза по прибытии',
      visa_easy: true,
      price_level: 1,
      price: 'недорого',
      kids: 'хорошо с детьми',
      kids_fit: 'good' as const,
      climate: { month: 'ноябрь', month_in: 'ноябре', day: 27, sea: 26 },
      highlights: ['коралловые рифы'],
      watch_out: ['ветрено'],
      why: `${name} подходит`,
      tradeoff: 'Ветрено вечером',
      flight: {
        price_rub: 12775,
        airline: 'NE',
        airline_name: 'Nesma Airlines',
        logo: 'https://pics.avs.io/64/64/NE.png',
        flight_number: 'NE 609',
        transfers: 0,
        hours: 5.5,
        departure: '2026-11-07 14:30',
        link: 'https://www.aviasales.ru/search/MOW0711HRG1',
        direct_available: true,
      },
    })
    streamReply(
      [
        { type: 'assistant_token', text: 'Вот что нашёл' },
        { type: 'destinations', summary: ['Море', 'Ноябрь'], cards: [card('hurghada', 'Хургада'), card('sharm', 'Шарм-эль-Шейх')] },
      ],
      { type: 'done', answer: 'Вот что нашёл', chat_id: 'chat-1', title: 'Море' },
    )
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'Море в ноябре{Enter}')

    expect(await screen.findByRole('heading', { name: 'Хургада' })).toBeInTheDocument()
    expect(screen.getByText('Шарм-эль-Шейх подходит')).toBeInTheDocument()
    expect(screen.getByText('Лучшее совпадение')).toBeInTheDocument()
    expect(screen.getAllByText('+26°')).toHaveLength(2)
    const ticket = screen.getAllByRole('link', { name: /Nesma Airlines/ })[0]
    expect(ticket).toHaveAttribute('href', 'https://www.aviasales.ru/search/MOW0711HRG1')
    expect(ticket).toHaveTextContent(/прямой · 5,5 ч/)
    expect(ticket).toHaveTextContent(/7 ноя, от/)
    expect(ticket).toHaveTextContent(/12\s775\s₽/)

    streamReply([], { type: 'done', answer: 'Отличный выбор', chat_id: 'chat-1', title: 'Море' })
    await userEvent.click(screen.getAllByRole('button', { name: 'Выбрать' })[1])

    await waitFor(() =>
      expect(sendChatStream).toHaveBeenLastCalledWith(
        expect.objectContaining({ query: 'Выбираю Шарм-эль-Шейх' }),
        expect.any(Function),
        expect.anything(),
      ),
    )
  })

  it('should draw a multi-city route as one wide card and send it when picked', async () => {
    const ticket = (price: number, airline: string) => ({
      price_rub: price,
      airline,
      airline_name: airline === 'KC' ? 'Air Astana' : 'Fly Arna',
      logo: `https://pics.avs.io/64/64/${airline}.png`,
      flight_number: `${airline} 1`,
      transfers: 0,
      hours: 4,
      departure: '2026-10-12 08:00',
      link: `https://www.aviasales.ru/${airline}`,
      direct_available: true,
    })
    const stop = (id: string, name: string, country: string, code: string) => ({
      id, name, country, country_code: code, kinds: ['city' as const], nights: 4, day: 20, sea: null,
      visa: 'без визы', visa_easy: true, highlights: ['старый город'],
    })
    streamReply(
      [
        { type: 'assistant_token', text: 'Вот маршруты' },
        {
          type: 'destinations',
          summary: ['Города', 'Несколько городов'],
          cards: [
            {
              type: 'route',
              id: 'tbilisi+yerevan',
              name: 'Тбилиси → Ереван',
              month: 'октябрь',
              month_in: 'октябре',
              stops: [stop('tbilisi', 'Тбилиси', 'Грузия', 'GE'), stop('yerevan', 'Ереван', 'Армения', 'AM')],
              legs: [
                { from: 'Астана', to: 'Тбилиси', mode: 'flight', km: 2500, hours: 4, ticket: ticket(30000, 'KC') },
                { from: 'Тбилиси', to: 'Ереван', mode: 'ground', km: 175, hours: 4, estimate: 'по земле' },
                { from: 'Ереван', to: 'Астана', mode: 'flight', km: 2600, hours: 4, ticket: ticket(28000, 'FA') },
              ],
              total_rub: 58000,
              total_complete: true,
              dates_chained: true,
              match: 92,
              interests: [{ kind: 'city', label: 'город', covered: true, wanted: true }],
              kids: 'хорошо с детьми',
              why: 'Два города и горы за одну поездку',
            },
          ],
        },
      ],
      { type: 'done', answer: 'Вот маршруты', chat_id: 'chat-1', title: 'Кавказ' },
    )
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'Хочу Ереван и Тбилиси{Enter}')

    expect(await screen.findByRole('heading', { name: 'Тбилиси' })).toBeInTheDocument()
    const card = screen.getByRole('heading', { name: 'Ереван' }).closest('article')!
    expect(card).toHaveClass('sm:col-span-2')
    expect(within(card).getByText('Два города и горы за одну поездку')).toBeInTheDocument()
    expect(within(card).getByText(/58\s000\s₽/)).toBeInTheDocument()
    expect(within(card).getByText('Даты состыкованы: 12 окт → 12 окт')).toBeInTheDocument()
    expect(within(card).queryByRole('link', { name: 'Астана → Тбилиси, Air Astana' })).toBeNull()

    await userEvent.click(within(card).getByRole('button', { name: 'Подробнее' }))
    const panel = await screen.findByRole('region', { name: 'Тбилиси → Ереван, подробнее' })
    expect(within(panel).getByRole('link', { name: 'Астана → Тбилиси, Air Astana' })).toHaveAttribute('href', 'https://www.aviasales.ru/KC')
    expect(within(panel).getByText(/по земле ~4 ч, 175 км/)).toBeInTheDocument()
    expect([...within(panel).getByRole('list', { name: 'Маршрут' }).children].map((li) => li.textContent)).toEqual([
      expect.stringContaining('Астана → Тбилиси'),
      expect.stringContaining('старый город'),
      expect.stringContaining('Тбилиси → Ереван'),
      expect.stringContaining('старый город'),
      expect.stringContaining('Ереван → Астана'),
    ])
    expect(within(panel).getByText('Грузия: без визы')).toBeInTheDocument()
    await userEvent.click(within(panel).getByRole('button', { name: 'Закрыть' }))

    streamReply([], { type: 'done', answer: 'Отлично', chat_id: 'chat-1', title: 'Кавказ' })
    await userEvent.click(within(card).getByRole('button', { name: 'Выбрать маршрут' }))
    await waitFor(() =>
      expect(sendChatStream).toHaveBeenLastCalledWith(
        expect.objectContaining({ query: 'Выбираю маршрут Тбилиси → Ереван' }),
        expect.any(Function),
        expect.anything(),
      ),
    )
  })

  it('should show answered questions from a saved chat as done', async () => {
    vi.mocked(client.fetchChatMeta).mockResolvedValue({
      id: 'c1',
      title: 'Море',
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    })
    vi.mocked(client.fetchChatMessages).mockResolvedValue({
      messages: [
        {
          id: 'm1',
          chat_id: 'c1',
          role: 'assistant',
          content: 'Уточню',
          trace: [
            {
              type: 'clarify',
              questions: [{ slot: 'budget', title: 'Какой бюджет?' }],
              prefill: { kinds: [], month: null, nights: null, adults: null, children: null, children_ages: [], budget_level: null },
            },
          ],
          created_at: '2026-10-24T10:00:00Z',
        },
        { id: 'm2', chat_id: 'c1', role: 'user', content: 'бюджет не важен', trace: [], created_at: '2026-10-24T10:00:01Z' },
      ],
    })
    renderChat('/chat/c1')

    expect(await screen.findByText('Уточнили: бюджет')).toBeInTheDocument()
    expect(screen.queryByText('Какой бюджет?')).toBeNull()
  })

  describe('a reply that failed', () => {
    const FAILED = 'Не получилось получить ответ. Попробуйте ещё раз чуть позже.'

    function failedTurn() {
      vi.mocked(client.fetchChatMeta).mockResolvedValue({
        id: 'c1',
        title: 'Мальдивы',
        created_at: '2026-10-26T00:16:00Z',
        updated_at: '2026-10-26T00:16:00Z',
      })
      vi.mocked(client.fetchChatMessages).mockResolvedValue({
        messages: [
          { id: 'm1', chat_id: 'c1', role: 'user', content: 'Мальдивы', trace: [], created_at: '2026-10-26T00:16:00Z' },
          { id: 'm2', chat_id: 'c1', role: 'assistant', content: FAILED, trace: [{ type: 'error', message: FAILED }], created_at: '2026-10-26T00:16:01Z' },
        ],
      })
    }

    it('should ask the same question again in place of the failed turn', async () => {
      failedTurn()
      streamReply([{ type: 'assistant_token', text: 'Вот Мальдивы' }], { type: 'done', answer: 'Вот Мальдивы', chat_id: 'c1', title: 'Мальдивы' })
      renderChat('/chat/c1')

      await userEvent.click(await screen.findByRole('button', { name: 'Повторить' }))

      expect(sendChatStream).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'Мальдивы', chat_id: 'c1', retry: true }),
        expect.any(Function),
        expect.anything(),
      )
      expect(await screen.findByText('Вот Мальдивы')).toBeInTheDocument()
      expect(screen.getAllByText('Мальдивы', { selector: 'div' })).toHaveLength(1)
      expect(screen.queryByText(FAILED)).toBeNull()
    })

    it('should keep the agent header over the error without an empty steps panel', async () => {
      failedTurn()
      renderChat('/chat/c1')

      expect(await screen.findByText(FAILED)).toBeInTheDocument()
      expect(screen.getByText('Не получилось ответить')).toBeInTheDocument()
      expect(screen.queryByText('Что делаю сейчас')).toBeNull()
      expect(screen.queryByText('развернуть')).toBeNull()
    })
  })

  describe('the trip plan', () => {
    const BOOKING: BookingEvent = {
      type: 'booking',
      number: '1S-ABC234',
      plan_message_id: 'm1',
      name: 'Анталья',
      dates: PLAN.dates,
      holder: 'Анна Смирнова',
      extras: [],
      total_rub: PLAN.costs.total,
      currency: PLAN.currency,
    }

    function savedPlan(status: Partial<TripStatus> = {}) {
      vi.mocked(client.fetchChatMeta).mockResolvedValue({
        id: 'c1',
        title: 'Анталья',
        created_at: '2026-10-25T10:00:00Z',
        updated_at: '2026-10-25T10:00:00Z',
        ...status,
      })
      vi.mocked(client.fetchChatMessages).mockResolvedValue({
        messages: [
          { id: 'm1', chat_id: 'c1', role: 'assistant', content: 'Собрал для вас неделю в Анталье.', trace: [PLAN], created_at: '2026-10-25T10:00:00Z' },
        ],
      })
    }

    it('should book the plan and keep the booking in the chat', async () => {
      savedPlan()
      vi.mocked(client.bookTrip).mockResolvedValue({
        id: 'm2',
        chat_id: 'c1',
        role: 'assistant',
        content: 'Поездка оформлена',
        trace: [BOOKING],
        created_at: '2026-10-25T10:05:00Z',
      })
      renderChat('/chat/c1')

      const plan = await screen.findByRole('article', { name: 'План поездки: Анталья' })
      await userEvent.click(within(plan).getByRole('button', { name: 'Оформить поездку' }))
      const sheet = await screen.findByRole('dialog', { name: 'Оформление поездки' })
      await userEvent.type(within(sheet).getByLabelText('Имя и фамилия'), 'Анна Смирнова')
      await userEvent.click(within(sheet).getByRole('button', { name: /Оплатить/ }))

      expect(client.bookTrip).toHaveBeenCalledWith('c1', { extras: [], holder: 'Анна Смирнова' })
      expect(await within(sheet).findByText('1S-ABC234')).toBeInTheDocument()
      await userEvent.click(within(sheet).getByRole('button', { name: 'Готово' }))

      expect(await screen.findByRole('article', { name: 'Бронь 1S-ABC234' })).toBeInTheDocument()
      expect(within(plan).getByText(/Оформлено/)).toHaveTextContent('1S-ABC234')
    })

    it('should not offer to book a plan whose dates have passed', async () => {
      savedPlan({ dates_passed: true })
      renderChat('/chat/c1')

      const plan = await screen.findByRole('article', { name: 'План поездки: Анталья' })

      expect(await screen.findByText('Даты поездки уже прошли')).toBeInTheDocument()
      expect(within(plan).queryByRole('button', { name: 'Оформить поездку' })).toBeNull()
    })

    it('should ask the agent for the other hotel picked on the plan', async () => {
      savedPlan()
      streamReply([], { type: 'done', answer: 'Поменял отель', chat_id: 'c1', title: 'Анталья' })
      renderChat('/chat/c1')

      const plan = await screen.findByRole('article', { name: 'План поездки: Анталья' })
      await userEvent.click(within(plan).getByRole('button', { name: 'Выбрать «Дом у маяка»' }))

      await waitFor(() =>
        expect(sendChatStream).toHaveBeenLastCalledWith(
          expect.objectContaining({ query: 'Хочу отель «Дом у маяка» вместо «Морской бриз»' }),
          expect.any(Function),
          expect.anything(),
        ),
      )
    })
  })
})
