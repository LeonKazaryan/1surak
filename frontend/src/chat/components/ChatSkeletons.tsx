import type { CSSProperties } from 'react'
import { useMatch } from 'react-router-dom'
import { ChevronLeftIcon, PlusIcon } from '@heroicons/react/20/solid'
import { LogoMark } from '@/components/LogoMark'
import { Skeleton } from '@/components/ui/skeleton'
import { getMyChats } from '../chatStorage'
import { readSidebarOpen } from '../sidebarCookie'

const RECENT_ROW_WIDTHS = ['78%', '62%', '70%', '54%']
const CHIP_WIDTHS = ['w-44', 'w-40', 'w-44']

function fade(step: number): CSSProperties {
  return { opacity: 1 - step * 0.2 }
}

export function RecentChatsSkeleton() {
  return (
    <div data-testid="recent-chats-skeleton" aria-hidden className="flex flex-col gap-1">
      {RECENT_ROW_WIDTHS.map((width, i) => (
        <div key={i} className="flex h-8 items-center px-2" style={fade(i)}>
          <Skeleton className="h-3.5" style={{ width }} />
        </div>
      ))}
    </div>
  )
}

export function MessagesSkeleton() {
  return (
    <div data-testid="messages-skeleton" aria-hidden className="flex h-full flex-col justify-end pt-4 pb-6">
      <div className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-6 max-md:px-4">
        {[2, 0].map((step) => (
          <div key={step} className="flex flex-col gap-6" style={fade(step)}>
            <div className="flex justify-end">
              <Skeleton className="h-11 w-[42%] rounded-2xl" />
            </div>
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <Skeleton className="h-7 w-7 rounded-lg" />
                <Skeleton className="h-3.5 w-32" />
              </div>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-[88%]" />
              <Skeleton className="h-4 w-[56%]" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ComposerSkeleton() {
  return (
    <div className="shrink-0 px-6 pt-2 pb-5 max-md:px-4">
      <div className="mx-auto flex max-w-[720px] flex-col items-center gap-2">
        <Skeleton className="h-[60px] w-full rounded-2xl" />
        <Skeleton className="h-3 w-48" />
      </div>
    </div>
  )
}

function EmptyChatSkeleton() {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 pt-6 pb-16 max-md:px-4">
      <div className="flex w-full max-w-[min(92vw,44rem)] flex-col items-center gap-5">
        <LogoMark className="h-14 w-14" />
        <Skeleton className="h-8 w-60 rounded-lg" />
        <div className="flex flex-wrap justify-center gap-2">
          {CHIP_WIDTHS.map((width, i) => (
            <Skeleton key={i} className={`h-9 rounded-full ${width}`} />
          ))}
        </div>
        <Skeleton className="h-[60px] w-full rounded-2xl" />
        <Skeleton className="h-4 w-[80%]" />
      </div>
    </div>
  )
}

export function ChatPageSkeleton() {
  const savedChat = useMatch('/chat/:chatId')

  return (
    <>
      <span role="status" className="sr-only">
        Загрузка
      </span>
      <div data-testid="chat-page-skeleton" aria-hidden className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex h-14 shrink-0 items-center gap-3 px-4">
          <Skeleton className="h-7 w-7 rounded-md" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="ml-auto h-8 w-36 rounded-lg" />
        </div>
        {savedChat ? (
          <>
            <div className="min-h-0 flex-1 overflow-hidden">
              <MessagesSkeleton />
            </div>
            <ComposerSkeleton />
          </>
        ) : (
          <EmptyChatSkeleton />
        )}
      </div>
    </>
  )
}

export function ChatShellSkeleton() {
  const sidebarOpen = readSidebarOpen()
  const hasRecentChats = getMyChats().length > 0

  return (
    <div data-testid="chat-skeleton" className="flex h-svh overflow-hidden bg-sidebar">
      {sidebarOpen && (
        <div aria-hidden className="hidden w-64 shrink-0 flex-col p-2 text-sm text-sidebar-foreground md:flex">
          <div className="p-2">
            <div className="flex h-12 items-center gap-2 p-2">
              <LogoMark className="h-8 w-8" />
              <span className="text-[15px] font-semibold tracking-tight">1surak</span>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <div className="p-2">
              <div className="flex h-8 items-center gap-2 px-2">
                <PlusIcon className="size-4 shrink-0" />
                Новый чат
              </div>
            </div>
            {hasRecentChats && (
              <div className="p-2">
                <div className="flex h-8 items-center px-2 text-xs font-medium text-sidebar-foreground/70">Недавние</div>
                <RecentChatsSkeleton />
              </div>
            )}
          </div>
          <div className="mt-auto p-2">
            <div className="flex h-8 items-center gap-2 px-2 text-muted-foreground">
              <ChevronLeftIcon className="size-4 shrink-0" />
              На главную
            </div>
          </div>
        </div>
      )}
      <div
        className={`flex min-w-0 flex-1 flex-col overflow-hidden bg-background md:m-2 md:rounded-xl md:shadow-sm ${sidebarOpen ? 'md:ml-0' : ''}`}
      >
        <ChatPageSkeleton />
      </div>
    </div>
  )
}
