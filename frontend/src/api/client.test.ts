import { afterEach, describe, expect, it, vi } from 'vitest'
import { deleteChat, fetchChatMessages, fetchChatMeta, fetchChats, sendChatStream } from './client'
import type { ChatStreamEvent } from '../types/api'

function streamOf(chunks: string[]): ReadableStream<Uint8Array<ArrayBuffer>> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
}

function mockFetch(response: Partial<Response>) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('sendChatStream', () => {
  it('should parse NDJSON events split across chunks and return the done payload', async () => {
    const done = { type: 'done', answer: 'Привет', chat_id: 'c1', title: 'Привет' }
    mockFetch({
      ok: true,
      body: streamOf([
        '{"type":"assistant_token","text":"При"}\n{"type":"assis',
        'tant_token","text":"вет"}\n',
        JSON.stringify(done),
      ]),
    })
    const events: ChatStreamEvent[] = []

    const result = await sendChatStream({ query: 'Привет' }, (e) => events.push(e))

    expect(events.map((e) => e.type)).toEqual(['assistant_token', 'assistant_token', 'done'])
    expect(result).toEqual(done)
  })

  it('should post the request body as JSON to the stream endpoint', async () => {
    const fetchMock = mockFetch({
      ok: true,
      body: streamOf(['{"type":"done","answer":"","chat_id":"c1","title":null}\n']),
    })

    await sendChatStream({ query: 'Казань', chat_id: 'c1' }, () => {})

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/chat/stream',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'Казань', chat_id: 'c1' }),
      }),
    )
  })

  it('should throw with the status when the response is not ok', async () => {
    mockFetch({ ok: false, status: 422, statusText: 'Unprocessable Entity' })

    await expect(sendChatStream({ query: 'x' }, () => {})).rejects.toThrow('422')
  })

  it('should throw when the stream ends without a done event', async () => {
    mockFetch({ ok: true, body: streamOf(['{"type":"assistant_token","text":"a"}\n']) })

    await expect(sendChatStream({ query: 'x' }, () => {})).rejects.toThrow('done')
  })

  it('should throw when the response has no body', async () => {
    mockFetch({ ok: true, body: null })

    await expect(sendChatStream({ query: 'x' }, () => {})).rejects.toThrow('body')
  })
})

describe('chat persistence calls', () => {
  it('should not call the network when listing zero chats', async () => {
    const fetchMock = mockFetch({ ok: true })

    await expect(fetchChats([])).resolves.toEqual({ items: [] })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('should request chats by comma-separated ids', async () => {
    const fetchMock = mockFetch({ ok: true, json: () => Promise.resolve({ items: [] }) })

    await fetchChats(['a', 'b'])

    expect(fetchMock).toHaveBeenCalledWith('/api/chats?ids=a%2Cb', undefined)
  })

  it('should fetch chat meta and messages by id', async () => {
    const fetchMock = mockFetch({ ok: true, json: () => Promise.resolve({ messages: [] }) })

    await fetchChatMeta('c1')
    await fetchChatMessages('c1')

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual(['/api/chats/c1', '/api/chats/c1/messages'])
  })

  it('should treat deleting a missing chat as success', async () => {
    mockFetch({ ok: false, status: 404, statusText: 'Not Found' })

    await expect(deleteChat('c1')).resolves.toBeUndefined()
  })

  it('should throw when deleting fails on the server', async () => {
    mockFetch({ ok: false, status: 500, statusText: 'Server Error' })

    await expect(deleteChat('c1')).rejects.toThrow('500')
  })
})
