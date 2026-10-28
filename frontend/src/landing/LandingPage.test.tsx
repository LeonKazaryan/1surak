import { render, screen, waitFor, within } from '@testing-library/react'
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
  fetchMemory: vi.fn().mockRejectedValue(new Error('offline')),
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

  const trip = (id: string, title: string) => ({ id, title, created_at: '2026-10-19T12:00:00Z', updated_at: '2026-10-19T12:00:00Z' })

  const openMenuButtons = async (firstTrip: string) => {
    await userEvent.click(await screen.findByRole('button', { name: 'Открыть меню' }))
    const menu = screen.getByRole('navigation', { name: 'Разделы' })
    await within(menu).findByRole('button', { name: firstTrip })
    return { menu, names: within(menu).getAllByRole('button').map((b) => b.textContent) }
  }

  it('should put the shortest of the last three trips beside the plan card and the rest below', async () => {
    localStorage.setItem('1surak.myChats', JSON.stringify(['c1', 'c2', 'c3', 'c4']))
    vi.mocked(client.fetchChats).mockResolvedValueOnce({
      items: [trip('c3', 'Таити'), trip('c2', 'Казань'), trip('c1', 'Хочу к тёплому морю в ноябре, недорого')],
    })
    renderApp()

    const { menu, names } = await openMenuButtons('Таити')
    expect(client.fetchChats).toHaveBeenCalledWith(['c1', 'c2', 'c3'])
    expect(names).toEqual(['Новая поездка', 'Все поездки', 'Таити', 'Хочу к тёплому морю в ноябре, недорого', 'Казань'])

    await userEvent.click(within(menu).getByRole('button', { name: 'Таити' }))
    await waitFor(() => expect(client.fetchChatMeta).toHaveBeenCalledWith('c3'))
  })

  it('should put the second trip below and all trips beside the title when there are two', async () => {
    localStorage.setItem('1surak.myChats', JSON.stringify(['c1', 'c2']))
    vi.mocked(client.fetchChats).mockResolvedValueOnce({ items: [trip('c1', 'Таити'), trip('c2', 'Казань')] })
    renderApp()

    const { names } = await openMenuButtons('Таити')
    expect(names).toEqual(['Новая поездка', 'Все поездки', 'Таити', 'Казань'])
  })

  it('should put all trips in the bottom row when there is one trip', async () => {
    localStorage.setItem('1surak.myChats', JSON.stringify(['c1']))
    vi.mocked(client.fetchChats).mockResolvedValueOnce({ items: [trip('c1', 'Таити')] })
    renderApp()

    const { names } = await openMenuButtons('Таити')
    expect(names).toEqual(['Новая поездка', 'Таити', 'Все поездки'])
  })

  it('should list all trips first and then the latest two on a phone', async () => {
    vi.stubGlobal('innerWidth', 390)
    localStorage.setItem('1surak.myChats', JSON.stringify(['c1', 'c2', 'c3']))
    vi.mocked(client.fetchChats).mockResolvedValueOnce({
      items: [trip('c1', 'Таити'), trip('c2', 'Казань'), trip('c3', 'Хочу к тёплому морю в ноябре, недорого')],
    })
    renderApp()

    const { names } = await openMenuButtons('Таити')
    expect(names).toEqual(['Новая поездка', 'Все поездки', 'Таити', 'Казань'])
    vi.unstubAllGlobals()
  })

  it('should keep my trips out of the menu before the first trip', async () => {
    renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Открыть меню' }))
    const menu = screen.getByRole('navigation', { name: 'Разделы' })
    expect(within(menu).getByRole('button', { name: 'Новая поездка' })).toBeInTheDocument()
    expect(within(menu).queryByText('Мои поездки')).toBeNull()
    expect(within(menu).queryByText('Агент')).toBeNull()
  })

  it('should stay on the landing page when the description is blank', async () => {
    renderApp()

    await userEvent.type(await screen.findByRole('textbox', { name: 'Опишите поездку' }), '   ')
    await userEvent.click(screen.getByRole('button', { name: 'Спланировать' }))

    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(sendChatStream).not.toHaveBeenCalled()
  })

  it('should start a new trip from the navigation menu', async () => {
    renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Открыть меню' }))
    await userEvent.click(screen.getByRole('button', { name: 'Новая поездка' }))

    expect(await screen.findByRole('heading', { name: 'Куда отправимся?' })).toBeInTheDocument()
    expect(sendChatStream).not.toHaveBeenCalled()
  })

  it('should keep the hero intro to one short line', async () => {
    renderApp()

    expect(await screen.findByText('Напишите как есть, агент соберёт остальное.')).toBeInTheDocument()
  })

  it('should show how it works instead of the track task list', async () => {
    renderApp()

    expect(await screen.findByRole('heading', { name: 'Как это работает' })).toBeInTheDocument()
    expect(screen.queryByTestId('brief-task')).not.toBeInTheDocument()
  })

  it('should send unknown routes back to the landing page', async () => {
    renderApp('/nope')

    expect(await screen.findByRole('heading', { level: 1, name: 'Вся поездка в одном сообщении' })).toBeInTheDocument()
  })
})
