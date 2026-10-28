import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '@/api/client'
import type { Idea, MemoryResponse } from '@/types/api'
import { IdeaChips } from './IdeaChips'
import { MemoryPanel } from './MemoryPanel'
import { useMemory } from './useMemory'

vi.mock('@/api/client', () => ({ fetchMemory: vi.fn() }))

const REMEMBERED: MemoryResponse = {
  facts: [
    { key: 'party', label: 'Кто едет', text: 'двое взрослых + ребёнок 6 лет', source: 'Хургада · ноябрь', chat_id: 'c1' },
    { key: 'wish:с видом на море', label: 'Важно', text: 'с видом на море', source: 'Хургада · ноябрь', chat_id: 'c1' },
  ],
  ideas: [
    { label: 'Анталья: через 12 дней', query: 'Что взять с собой?', chat_id: 'c2', why: 'бронь 1S-XYZ789' },
    { label: 'Море в декабре с детьми', query: 'Хочу к тёплому морю в декабре, двое взрослых и ребёнок 6 лет', why: 'помню: двое взрослых + ребёнок 6 лет' },
    { label: 'Выходные недалеко', query: 'Куда поехать на выходные недалеко в декабре?', why: null },
  ],
}

function StartScreen({ onPick }: { onPick: (idea: Idea) => void }) {
  const memory = useMemory()
  return (
    <>
      <IdeaChips ideas={memory.ideas} failed={memory.failed} onPick={onPick} />
      <MemoryPanel facts={memory.facts} onForget={memory.forget} />
    </>
  )
}

beforeEach(() => {
  localStorage.clear()
  vi.mocked(client.fetchMemory).mockReset()
})

describe('Memory on the start screen', () => {
  it('should suggest ideas from earlier trips and say what each comes from', async () => {
    localStorage.setItem('1surak.myChats', JSON.stringify(['c1', 'c2']))
    vi.mocked(client.fetchMemory).mockResolvedValue(REMEMBERED)
    const onPick = vi.fn()
    render(<StartScreen onPick={onPick} />)

    const row = screen.getByRole('group', { name: 'Идеи для поездки' })
    const soon = await within(row).findByRole('button', { name: /Анталья: через 12 дней/ })
    expect(soon).toHaveTextContent('бронь 1S-XYZ789')
    expect(within(row).getByRole('button', { name: /Выходные недалеко/ })).not.toHaveTextContent('помню')
    expect(client.fetchMemory).toHaveBeenCalledWith(['c1', 'c2'], [], expect.anything())

    await userEvent.click(within(row).getByRole('button', { name: /Море в декабре с детьми/ }))
    expect(onPick).toHaveBeenCalledWith(REMEMBERED.ideas[1])
  })

  it('should list what it remembers and forget a fact for good', async () => {
    // like the server: a hidden fact is not in the answer
    vi.mocked(client.fetchMemory).mockImplementation(async (_, forget) => ({
      ...REMEMBERED,
      facts: REMEMBERED.facts.filter((f) => !forget.includes(f.key)),
    }))
    render(<StartScreen onPick={() => {}} />)

    await userEvent.click(await screen.findByRole('button', { name: /Что я о вас помню/ }))
    const panel = await screen.findByRole('dialog', { name: 'Что я о вас помню' })
    expect(within(panel).getByText('двое взрослых + ребёнок 6 лет')).toBeInTheDocument()
    expect(within(panel).getAllByText('Хургада · ноябрь')).toHaveLength(2)

    await userEvent.click(within(panel).getByRole('button', { name: 'Забыть: двое взрослых + ребёнок 6 лет' }))

    await waitFor(() => expect(within(panel).queryByText('двое взрослых + ребёнок 6 лет')).toBeNull())
    expect(JSON.parse(localStorage.getItem('1surak.forgotten') ?? '[]')).toEqual(['party'])
    await waitFor(() => expect(client.fetchMemory).toHaveBeenLastCalledWith([], ['party'], expect.anything()))
  })

  it('should show nothing about memory when there are no trips yet', async () => {
    vi.mocked(client.fetchMemory).mockResolvedValue({ facts: [], ideas: [{ label: 'Тёплое море в декабре', query: 'Хочу к морю', why: null }] })
    render(<StartScreen onPick={() => {}} />)

    expect(await screen.findByRole('button', { name: 'Тёплое море в декабре' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Что я о вас помню/ })).toBeNull()
  })
})
