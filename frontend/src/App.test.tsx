import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '@/api/client'
import { AppRoutes } from './App'

vi.mock('@/api/client', () => ({
  sendChatStream: vi.fn(),
  fetchChats: vi.fn(),
  fetchChatMeta: vi.fn(),
  fetchChatMessages: vi.fn(),
  deleteChat: vi.fn(),
}))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
  vi.mocked(client.fetchChats).mockReturnValue(new Promise(() => {}))
  vi.mocked(client.fetchChatMeta).mockReturnValue(new Promise(() => {}))
  vi.mocked(client.fetchChatMessages).mockReturnValue(new Promise(() => {}))
})

describe('AppRoutes', () => {
  it('should render the landing text right away, with no placeholders', () => {
    renderAt('/')

    expect(screen.getByRole('heading', { level: 1, name: 'Вся поездка в одном сообщении' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Опишите поездку' })).toBeInTheDocument()
    expect(document.querySelector('[data-slot="skeleton"]')).toBeNull()
  })

  it('should render the empty chat screen right away, with no placeholders', () => {
    renderAt('/chat')

    expect(screen.getByRole('heading', { level: 1, name: 'Куда отправимся?' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Сообщение агенту' })).toBeInTheDocument()
    expect(document.querySelector('[data-slot="skeleton"]')).toBeNull()
  })

  it('should keep the header and composer real while a saved chat loads', () => {
    localStorage.setItem('1surak.myChats', JSON.stringify(['c1']))
    renderAt('/chat/c1')

    expect(screen.getByRole('button', { name: 'План поездки' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Сообщение агенту' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Новый чат' })).toBeInTheDocument()
    expect(screen.getByTestId('messages-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('recent-chats-skeleton')).toBeInTheDocument()
  })
})
