import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, type InitialEntry } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatLayout from './ChatLayout'
import ChatPage from './ChatPage'
import * as client from '@/api/client'
import type { ChatStreamDone, ChatStreamEvent } from '@/types/api'

vi.mock('@/api/client', () => ({
  sendChatStream: vi.fn(),
  fetchChats: vi.fn().mockResolvedValue({ items: [] }),
  fetchChatMeta: vi.fn(),
  fetchChatMessages: vi.fn(),
  deleteChat: vi.fn().mockResolvedValue(undefined),
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

describe('ChatPage', () => {
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
    localStorage.setItem('1surak.departureCity', 'KZN')
    streamReply([], { type: 'done', answer: 'Ок', chat_id: 'chat-1', title: 'Море' })
    renderChat({ pathname: '/chat', state: { query: 'Хочу к морю' } })

    await waitFor(() =>
      expect(sendChatStream).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'Хочу к морю', origin: 'Казань' }),
        expect.any(Function),
        expect.anything(),
      ),
    )
  })

  it('should show example trips in the empty state', () => {
    renderChat()

    expect(screen.getByRole('button', { name: 'Тёплое море в ноябре' })).toBeInTheDocument()
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

  it('should resize the trip plan panel with the keyboard and the mouse', async () => {
    renderChat()
    await userEvent.click(screen.getByRole('button', { name: /План поездки/ }))
    const separator = screen.getByRole('separator')
    const panelWidth = () => (separator.nextElementSibling as HTMLElement).style.getPropertyValue('--plan-w')

    fireEvent.keyDown(separator, { key: 'Home' })
    expect(panelWidth()).toBe('560px')

    fireEvent.keyDown(separator, { key: 'ArrowRight' })
    expect(panelWidth()).toBe('536px')

    fireEvent.mouseDown(separator, { clientX: 500 })
    fireEvent.mouseMove(document, { clientX: 600 })
    fireEvent.mouseUp(document)
    expect(panelWidth()).toBe('436px')
    expect(localStorage.getItem('chat.planPanelWidth')).toBe('436')

    fireEvent.doubleClick(separator)
    expect(panelWidth()).toBe('380px')
  })

  it('should open and close the trip plan panel', async () => {
    renderChat()

    await userEvent.click(screen.getByRole('button', { name: /План поездки/ }))
    expect(screen.getByRole('region', { name: 'План поездки' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Скрыть план/ }))
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

  it('should ask only the missing questions as cards and send the answers in one message', async () => {
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
          prefill: { kinds: ['sea'], month: 11, nights: null, adults: null, children: 1, children_ages: [], budget_level: null },
        },
      ],
      { type: 'done', answer: 'Уточню пару моментов', chat_id: 'chat-1', title: 'Море' },
    )
    renderChat()
    await userEvent.type(screen.getByRole('textbox'), 'К морю с ребёнком, недорого{Enter}')

    expect(await screen.findByText('Кто едет?')).toBeInTheDocument()
    expect(screen.getByText('Вы написали «недорого»')).toBeInTheDocument()
    expect(screen.queryByText('Какой отдых хочется?')).toBeNull()
    const submit = await screen.findByRole('button', { name: /Подобрать направления/ })
    expect(submit).toBeDisabled()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Возраст ребёнка 1' }), '5')
    await userEvent.click(screen.getByRole('button', { name: /Средне/ }))
    streamReply([], { type: 'done', answer: 'Ищу', chat_id: 'chat-1', title: 'Море' })
    await userEvent.click(submit)

    await waitFor(() => expect(sendChatStream).toHaveBeenCalledTimes(2))
    expect(sendChatStream).toHaveBeenLastCalledWith(
      expect.objectContaining({
        query: '2 взрослых + 1 ребёнок (5 лет) · бюджет: средне',
        answers: { adults: 2, children: 1, children_ages: [5], budget_level: 2 },
      }),
      expect.any(Function),
      expect.anything(),
    )
    expect(await screen.findByText('Уточнили: кто едет, бюджет')).toBeInTheDocument()
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
    expect(screen.getAllByText('4,5 ч · прямой')).toHaveLength(2)

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
})
