import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeftIcon, PlusIcon, TrashIcon } from '@heroicons/react/20/solid'
import { Wordmark } from '@/components/Logo'
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
import { cn } from '@/components/ui/utils'
import type { ChatMeta } from '@/types/api'
import { RecentChatsSkeleton } from './components/ChatSkeletons'
import { ConfirmDeleteDialog } from './components/ConfirmDeleteDialog'
import { shortDate } from './components/ticketFormat'

const UNTITLED = 'Новая поездка'

/** The line under a trip's title: why it needs a look, or else when it is and where it flies from. */
function tripLine(chat: ChatMeta): { text: string; warn: boolean } | null {
  if (chat.dates_passed) return { text: 'Даты прошли', warn: true }
  if (chat.stale && chat.priced_at) return { text: `Цены от ${shortDate(chat.priced_at)}`, warn: true }
  const summary = chat.summary ?? []
  // the first chip is the kind of trip or the place, which the title already says
  const parts = [summary[1] ?? summary[0], chat.departure].filter(Boolean)
  return parts.length ? { text: parts.join(' · '), warn: false } : null
}

interface ChatSidebarProps {
  recentChats: ChatMeta[]
  recentLoading: boolean
  activeChatId: string | null
  onDeleteChat: (chatId: string) => void
}

export function ChatSidebar({ recentChats, recentLoading, activeChatId, onDeleteChat }: ChatSidebarProps) {
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
                <Link to="/" onClick={closeOnMobile} viewTransition>
                  <span className="flex size-8 shrink-0">
                    <LogoMark className="h-8 w-8" />
                  </span>
                  <Wordmark />
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Новая поездка">
                  <Link to="/chat" onClick={closeOnMobile} viewTransition>
                    <PlusIcon />
                    <span>Новая поездка</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroup>

          {(recentLoading || recentChats.length > 0) && (
            <SidebarGroup>
              <SidebarGroupLabel>Мои поездки</SidebarGroupLabel>
              {recentLoading ? (
                <RecentChatsSkeleton />
              ) : (
                <SidebarMenu>
                  {recentChats.map((chat) => {
                    const line = tripLine(chat)
                    return (
                      <SidebarMenuItem key={chat.id}>
                        <SidebarMenuButton
                          asChild
                          size={line ? 'lg' : 'default'}
                          isActive={chat.id === activeChatId}
                          title={chat.title ?? UNTITLED}
                        >
                          <Link to={`/chat/${chat.id}`} onClick={closeOnMobile} viewTransition>
                            <span className="flex min-w-0 flex-col">
                              <span className="truncate">{chat.title ?? UNTITLED}</span>
                              {line && (
                                <span
                                  className={cn(
                                    'truncate text-[12px] font-normal',
                                    line.warn ? 'text-amber-600' : 'text-muted-foreground',
                                  )}
                                >
                                  {line.text}
                                </span>
                              )}
                            </span>
                          </Link>
                        </SidebarMenuButton>
                        <SidebarMenuAction
                          showOnHover
                          aria-label="Удалить поездку"
                          onClick={() => setDeleteTarget(chat)}
                          className="hover:bg-danger-soft hover:text-danger"
                        >
                          <TrashIcon />
                        </SidebarMenuAction>
                      </SidebarMenuItem>
                    )
                  })}
                </SidebarMenu>
              )}
            </SidebarGroup>
          )}
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild className="text-muted-foreground">
                <Link to="/" onClick={closeOnMobile} viewTransition>
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
