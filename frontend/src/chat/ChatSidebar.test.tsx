import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatLayout from './ChatLayout'
import * as client from '@/api/client'

vi.mock('@/api/client', () => ({
  sendChatStream: vi.fn(),
  fetchChats: vi.fn(),
  fetchChatMeta: vi.fn(),
  fetchChatMessages: vi.fn(),
  deleteChat: vi.fn(),
  fetchMemory: vi.fn().mockRejectedValue(new Error('offline')),
}))

const chats = [
  { id: 'c1', title: 'Море в ноябре', created_at: '2026-10-24T10:00:00Z', updated_at: '2026-10-24T10:00:00Z' },
  { id: 'c2', title: 'Казань', created_at: '2026-10-24T09:00:00Z', updated_at: '2026-10-24T09:00:00Z' },
]

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={['/chat']}>
      <Routes>
        <Route path="/" element={<p>landing-page</p>} />
        <Route path="/chat" element={<ChatLayout />}>
          <Route index element={<p>chat-page</p>} />
          <Route path=":chatId" element={<p>saved-chat-page</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

function sidebar() {
  return within(screen.getByTestId('chat-sidebar'))
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  localStorage.setItem('1surak.myChats', JSON.stringify(['c2', 'c1']))
  vi.mocked(client.fetchChats).mockResolvedValue({ items: chats })
  vi.mocked(client.deleteChat).mockResolvedValue(undefined)
})

describe('ChatSidebar', () => {
  it('should show placeholder rows while recent chats load', async () => {
    let resolve!: (value: { items: typeof chats }) => void
    vi.mocked(client.fetchChats).mockReturnValue(new Promise((r) => (resolve = r)))
    renderLayout()

    expect(sidebar().getByTestId('recent-chats-skeleton')).toBeInTheDocument()
    resolve({ items: chats })
    expect(await sidebar().findByText('Казань')).toBeInTheDocument()
    expect(sidebar().queryByTestId('recent-chats-skeleton')).not.toBeInTheDocument()
  })

  it('should drop the placeholder rows when recent chats fail to load', async () => {
    vi.mocked(client.fetchChats).mockRejectedValue(new Error('offline'))
    renderLayout()

    await waitFor(() => expect(sidebar().queryByTestId('recent-chats-skeleton')).not.toBeInTheDocument())
  })

  it('should not show placeholder rows when no chats are saved', () => {
    localStorage.clear()
    renderLayout()

    expect(sidebar().queryByTestId('recent-chats-skeleton')).not.toBeInTheDocument()
  })

  it('should list recent chats in the stored order', async () => {
    renderLayout()

    await sidebar().findByText('Казань')
    const titles = sidebar()
      .getAllByRole('link')
      .map((link) => link.textContent)
      .filter((text) => text === 'Казань' || text === 'Море в ноябре')
    expect(titles).toEqual(['Казань', 'Море в ноябре'])
  })

  it('should open a saved chat from the list', async () => {
    renderLayout()

    await userEvent.click(await sidebar().findByRole('link', { name: 'Казань' }))

    expect(screen.getByText('saved-chat-page')).toBeInTheDocument()
  })

  it('should delete a chat after confirmation', async () => {
    renderLayout()
    await sidebar().findByText('Казань')

    await userEvent.click(sidebar().getAllByRole('button', { name: 'Удалить поездку' })[0])
    await userEvent.click(await screen.findByRole('button', { name: 'Удалить' }))

    await waitFor(() => expect(sidebar().queryByText('Казань')).toBeNull())
    expect(client.deleteChat).toHaveBeenCalledWith('c2')
    expect(JSON.parse(localStorage.getItem('1surak.myChats') ?? '[]')).toEqual(['c1'])
  })

  it('should keep the chat when deletion is cancelled', async () => {
    renderLayout()
    await sidebar().findByText('Казань')

    await userEvent.click(sidebar().getAllByRole('button', { name: 'Удалить поездку' })[0])
    await userEvent.click(await screen.findByRole('button', { name: 'Отмена' }))

    expect(sidebar().getByText('Казань')).toBeInTheDocument()
    expect(client.deleteChat).not.toHaveBeenCalled()
  })

  it('should call the list trips, not chats', async () => {
    renderLayout()

    expect(sidebar().getByRole('link', { name: 'Новая поездка' })).toBeInTheDocument()
    expect(await sidebar().findByText('Мои поездки')).toBeInTheDocument()
  })

  it('should show when the trip is and the departure city under each trip', async () => {
    vi.mocked(client.fetchChats).mockResolvedValue({
      items: [{ ...chats[1], summary: ['Казань', 'Январь · 2 ночи', '2 взрослых'], departure: 'из Астаны' }],
    })
    renderLayout()

    expect(await sidebar().findByText('Январь · 2 ночи · из Астаны')).toBeInTheDocument()
  })

  it('should mark a trip whose prices are old', async () => {
    vi.mocked(client.fetchChats).mockResolvedValue({
      items: [{ ...chats[1], summary: ['Казань'], stale: true, priced_at: '2026-10-19T12:00:00+00:00' }],
    })
    renderLayout()

    expect(await sidebar().findByText('Цены от 19 окт')).toBeInTheDocument()
  })

  it('should link back to the landing page', async () => {
    renderLayout()

    await userEvent.click(sidebar().getByRole('link', { name: 'На главную' }))

    expect(screen.getByText('landing-page')).toBeInTheDocument()
  })
})
