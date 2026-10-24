import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { deleteChat, fetchChats } from '@/api/client'
import type { ChatMeta } from '@/types/api'
import { getMyChats, removeMyChat } from './chatStorage'
import { ChatSidebar } from './ChatSidebar'
import type { ChatLayoutContext, WorkspaceChatMessage } from './types'

function readSidebarOpen(): boolean {
  const match = document.cookie.match(/(?:^|;\s*)sidebar_state=([^;]+)/)
  return match ? match[1] === 'true' : true
}

function inStoredOrder(items: ChatMeta[], ids: string[]): ChatMeta[] {
  const order = new Map(ids.map((id, i) => [id, i]))
  return [...items].sort((a, b) => (order.get(a.id) ?? ids.length) - (order.get(b.id) ?? ids.length))
}

export default function ChatLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [chatMessages, setMessages] = useState<WorkspaceChatMessage[]>([])
  const [planPanelOpen, setPlanPanelOpen] = useState(false)
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [recentChats, setRecentChats] = useState<ChatMeta[]>([])
  const [recentLoading, setRecentLoading] = useState(() => getMyChats().length > 0)

  useEffect(() => {
    const ids = getMyChats()
    if (!ids.length) return
    fetchChats(ids)
      .then(({ items }) => setRecentChats(inStoredOrder(items, ids)))
      .catch(() => setRecentChats([]))
      .finally(() => setRecentLoading(false))
  }, [])

  const handleDeleteChat = useCallback(
    (chatId: string) => {
      removeMyChat(chatId)
      setRecentChats((prev) => prev.filter((c) => c.id !== chatId))
      if (pathname.includes(chatId)) navigate('/chat', { replace: true })
      deleteChat(chatId).catch(() => {
        // Already removed locally; a failed server delete only leaves an orphan row.
      })
    },
    [pathname, navigate],
  )

  const ctx: ChatLayoutContext = {
    chatMessages,
    setMessages,
    planPanelOpen,
    setPlanPanelOpen,
    activeChatId,
    setActiveChatId,
    setRecentChats,
  }

  return (
    <SidebarProvider defaultOpen={readSidebarOpen()} className="h-svh overflow-hidden">
      <ChatSidebar
        recentChats={recentChats}
        recentLoading={recentLoading}
        activeChatId={activeChatId}
        onDeleteChat={handleDeleteChat}
      />
      <SidebarInset className="min-w-0 overflow-hidden">
        <Outlet context={ctx} />
      </SidebarInset>
    </SidebarProvider>
  )
}
