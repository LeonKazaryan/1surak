/** localStorage list of "my" chat ids, newest first (no auth). */

const KEY = '1surak.myChats'
const MAX_CHATS = 50

export function getMyChats(): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === 'string') : []
  } catch {
    return []
  }
}

function save(ids: string[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(ids))
  } catch {
    // Storage full or blocked (private mode): recent chats simply won't survive a reload.
  }
}

export function addMyChat(id: string): void {
  save([id, ...getMyChats().filter((c) => c !== id)].slice(0, MAX_CHATS))
}

export function removeMyChat(id: string): void {
  save(getMyChats().filter((c) => c !== id))
}
