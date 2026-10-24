import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { ChatShellSkeleton } from './ChatSkeletons'

function renderShell() {
  return render(
    <MemoryRouter initialEntries={['/chat']}>
      <ChatShellSkeleton />
    </MemoryRouter>,
  )
}

afterEach(() => {
  document.cookie = 'sidebar_state=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

describe('ChatShellSkeleton', () => {
  it('should draw the sidebar placeholder when the sidebar is open', () => {
    renderShell()

    expect(within(screen.getByTestId('chat-skeleton')).getByText('Новый чат')).toBeInTheDocument()
  })

  it('should leave the sidebar out when the user collapsed it', () => {
    document.cookie = 'sidebar_state=false; path=/'
    renderShell()

    expect(within(screen.getByTestId('chat-skeleton')).queryByText('Новый чат')).toBeNull()
  })

  it('should tell screen readers the page is loading', () => {
    renderShell()

    expect(screen.getByRole('status')).toHaveTextContent('Загрузка')
  })
})
