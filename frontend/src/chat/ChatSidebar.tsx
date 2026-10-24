import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronLeftIcon, PlusIcon, TrashIcon } from '@heroicons/react/20/solid'
import { LogoMark } from '@/components/LogoMark'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'
import type { ChatMeta } from '@/types/api'
import { RecentChatsSkeleton } from './components/ChatSkeletons'
import { ConfirmDeleteDialog } from './components/ConfirmDeleteDialog'

const UNTITLED = 'Новый чат'

interface ChatSidebarProps {
  recentChats: ChatMeta[]
  recentLoading: boolean
  activeChatId: string | null
  onDeleteChat: (chatId: string) => void
}

export function ChatSidebar({ recentChats, recentLoading, activeChatId, onDeleteChat }: ChatSidebarProps) {
  const { pathname } = useLocation()
  const { setOpenMobile } = useSidebar()
  const [deleteTarget, setDeleteTarget] = useState<ChatMeta | null>(null)
  const closeOnMobile = () => setOpenMobile(false)

  return (
    <>
      <Sidebar variant="inset" collapsible="offcanvas" data-testid="chat-sidebar">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild>
                <Link to="/" onClick={closeOnMobile}>
                  <span className="flex size-8 shrink-0">
                    <LogoMark className="h-8 w-8" />
                  </span>
                  <span className="text-[15px] font-semibold tracking-tight">1surak</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={pathname === '/chat'} tooltip="Новый чат">
                  <Link to="/chat" onClick={closeOnMobile}>
                    <PlusIcon />
                    <span>Новый чат</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroup>

          {(recentLoading || recentChats.length > 0) && (
            <SidebarGroup>
              <SidebarGroupLabel>Недавние</SidebarGroupLabel>
              {recentLoading ? (
                <RecentChatsSkeleton />
              ) : (
                <SidebarMenu>
                  {recentChats.map((chat) => (
                    <SidebarMenuItem key={chat.id}>
                      <SidebarMenuButton asChild isActive={chat.id === activeChatId} title={chat.title ?? UNTITLED}>
                        <Link to={`/chat/${chat.id}`} onClick={closeOnMobile}>
                          <span>{chat.title ?? UNTITLED}</span>
                        </Link>
                      </SidebarMenuButton>
                      <SidebarMenuAction
                        showOnHover
                        aria-label="Удалить чат"
                        onClick={() => setDeleteTarget(chat)}
                        className="hover:bg-danger-soft hover:text-danger"
                      >
                        <TrashIcon />
                      </SidebarMenuAction>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              )}
            </SidebarGroup>
          )}
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild className="text-muted-foreground">
                <Link to="/" onClick={closeOnMobile}>
                  <ChevronLeftIcon />
                  <span>На главную</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

      <ConfirmDeleteDialog
        chatTitle={deleteTarget?.title ?? null}
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) onDeleteChat(deleteTarget.id)
          setDeleteTarget(null)
        }}
      />
    </>
  )
}
