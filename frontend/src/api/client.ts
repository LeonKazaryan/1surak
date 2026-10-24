import type { ChatMessageOut, ChatMeta, ChatRequest, ChatStreamDone, ChatStreamEvent } from '../types/api'

const BASE = '/api'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

function isStreamEvent(value: unknown): value is ChatStreamEvent {
  return typeof value === 'object' && value !== null && typeof (value as { type?: unknown }).type === 'string'
}

async function* readNdjson(body: ReadableStream<Uint8Array>): AsyncGenerator<unknown> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.trim()) yield JSON.parse(line)
    }
  }
  if (buffer.trim()) yield JSON.parse(buffer)
}

/** Streams agent events from POST /api/chat/stream and resolves with the final `done` payload. */
export async function sendChatStream(
  body: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  options?: { signal?: AbortSignal },
): Promise<ChatStreamDone> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: options?.signal,
  })
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  if (!res.body) {
    throw new Error('No response body')
  }
  let done: ChatStreamDone | null = null
  for await (const value of readNdjson(res.body)) {
    if (!isStreamEvent(value)) continue
    onEvent(value)
    if (value.type === 'done') done = value
  }
  if (!done) {
    throw new Error('Stream ended without a done event')
  }
  return done
}

export function fetchChats(ids: string[]): Promise<{ items: ChatMeta[] }> {
  if (!ids.length) return Promise.resolve({ items: [] })
  return request<{ items: ChatMeta[] }>(`${BASE}/chats?ids=${encodeURIComponent(ids.join(','))}`)
}

export function fetchChatMeta(chatId: string): Promise<ChatMeta> {
  return request<ChatMeta>(`${BASE}/chats/${encodeURIComponent(chatId)}`)
}

export function fetchChatMessages(chatId: string): Promise<{ messages: ChatMessageOut[] }> {
  return request<{ messages: ChatMessageOut[] }>(`${BASE}/chats/${encodeURIComponent(chatId)}/messages`)
}

export async function deleteChat(chatId: string): Promise<void> {
  const res = await fetch(`${BASE}/chats/${encodeURIComponent(chatId)}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 404) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
}
