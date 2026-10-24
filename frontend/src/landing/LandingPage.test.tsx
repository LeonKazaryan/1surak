import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from '@/App'
import * as client from '@/api/client'

vi.mock('@/api/client', () => ({
  sendChatStream: vi.fn(),
  fetchChats: vi.fn().mockResolvedValue({ items: [] }),
  fetchChatMeta: vi.fn(),
  fetchChatMessages: vi.fn(),
  deleteChat: vi.fn(),
}))

const sendChatStream = vi.mocked(client.sendChatStream)

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
  sendChatStream.mockReset()
  sendChatStream.mockResolvedValue({ type: 'done', answer: 'Ок', chat_id: 'chat-1', title: 'Поездка' })
})

describe('LandingPage', () => {
  it('should state the product promise in the main heading', async () => {
    renderApp()

    expect(await screen.findByRole('heading', { level: 1, name: 'Вся поездка в одном сообщении' })).toBeInTheDocument()
  })

  it('should open a chat and send the typed trip description', async () => {
    renderApp()

    await userEvent.type(await screen.findByRole('textbox', { name: 'Опишите поездку' }), 'Казань на выходные')
    await userEvent.click(screen.getByRole('button', { name: 'Спланировать' }))

    await waitFor(() =>
      expect(sendChatStream).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'Казань на выходные' }),
        expect.any(Function),
        expect.anything(),
      ),
    )
    expect(await screen.findByText('Ок')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Сообщение агенту' })).toBeInTheDocument()
  })

  it('should send the full example query when an example chip is picked', async () => {
    renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Тёплое море в ноябре' }))

    await waitFor(() =>
      expect(sendChatStream).toHaveBeenCalledWith(
        expect.objectContaining({
          query: 'Хочу к тёплому морю в ноябре, недорого, с ребёнком, без долгих перелётов',
        }),
        expect.any(Function),
        expect.anything(),
      ),
    )
  })

  it('should stay on the landing page when the description is blank', async () => {
    renderApp()

    await userEvent.type(await screen.findByRole('textbox', { name: 'Опишите поездку' }), '   ')
    await userEvent.click(screen.getByRole('button', { name: 'Спланировать' }))

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(sendChatStream).not.toHaveBeenCalled()
  })

  it('should open a new chat from the navigation menu', async () => {
    renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Открыть меню' }))
    await userEvent.click(screen.getByRole('button', { name: 'Новый чат' }))

    expect(await screen.findByRole('heading', { name: 'Куда отправимся?' })).toBeInTheDocument()
    expect(sendChatStream).not.toHaveBeenCalled()
  })

  it('should list all six tasks of the track', async () => {
    renderApp()

    expect(await screen.findAllByTestId('brief-task')).toHaveLength(6)
  })

  it('should send unknown routes back to the landing page', async () => {
    renderApp('/nope')

    expect(await screen.findByRole('heading', { level: 1, name: 'Вся поездка в одном сообщении' })).toBeInTheDocument()
  })
})
