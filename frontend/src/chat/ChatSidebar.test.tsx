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

    await userEvent.click(sidebar().getAllByRole('button', { name: 'Удалить чат' })[0])
    await userEvent.click(await screen.findByRole('button', { name: 'Удалить' }))

    await waitFor(() => expect(sidebar().queryByText('Казань')).toBeNull())
    expect(client.deleteChat).toHaveBeenCalledWith('c2')
    expect(JSON.parse(localStorage.getItem('1surak.myChats') ?? '[]')).toEqual(['c1'])
  })

  it('should keep the chat when deletion is cancelled', async () => {
    renderLayout()
    await sidebar().findByText('Казань')

    await userEvent.click(sidebar().getAllByRole('button', { name: 'Удалить чат' })[0])
    await userEvent.click(await screen.findByRole('button', { name: 'Отмена' }))

    expect(sidebar().getByText('Казань')).toBeInTheDocument()
    expect(client.deleteChat).not.toHaveBeenCalled()
  })

  it('should link back to the landing page', async () => {
    renderLayout()

    await userEvent.click(sidebar().getByRole('link', { name: 'На главную' }))

    expect(screen.getByText('landing-page')).toBeInTheDocument()
  })
})
