import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppRoutes } from './App'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
})

describe('AppRoutes', () => {
  it('should show a landing skeleton while the landing page code loads', async () => {
    renderAt('/')

    expect(screen.getByTestId('landing-skeleton')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 1, name: 'Вся поездка в одном сообщении' })).toBeInTheDocument()
    expect(screen.queryByTestId('landing-skeleton')).not.toBeInTheDocument()
  })

  it('should show a chat skeleton while the chat code loads', async () => {
    renderAt('/chat')

    expect(screen.getByTestId('chat-skeleton')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 1, name: 'Куда отправимся?' })).toBeInTheDocument()
    expect(screen.queryByTestId('chat-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByTestId('chat-page-skeleton')).not.toBeInTheDocument()
  })
})
