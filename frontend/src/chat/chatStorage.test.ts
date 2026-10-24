import { beforeEach, describe, expect, it } from 'vitest'
import { addMyChat, getMyChats, removeMyChat } from './chatStorage'

const KEY = '1surak.myChats'

beforeEach(() => {
  localStorage.clear()
})

describe('chatStorage', () => {
  it('should return an empty list when nothing is stored', () => {
    expect(getMyChats()).toEqual([])
  })

  it('should put the newest chat first without duplicates', () => {
    addMyChat('a')
    addMyChat('b')
    addMyChat('a')

    expect(getMyChats()).toEqual(['a', 'b'])
  })

  it('should keep at most 50 chats', () => {
    Array.from({ length: 60 }, (_, i) => addMyChat(`chat-${i}`))

    const chats = getMyChats()
    expect(chats).toHaveLength(50)
    expect(chats[0]).toBe('chat-59')
  })

  it('should remove a chat', () => {
    addMyChat('a')
    addMyChat('b')

    removeMyChat('a')

    expect(getMyChats()).toEqual(['b'])
  })

  it('should ignore corrupted storage', () => {
    localStorage.setItem(KEY, '{not json')
    expect(getMyChats()).toEqual([])

    localStorage.setItem(KEY, JSON.stringify({ a: 1 }))
    expect(getMyChats()).toEqual([])
  })
})
