import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ChatPageSkeleton, ChatShellSkeleton } from '@/chat/components/ChatSkeletons'
import { LandingSkeleton } from '@/landing/LandingSkeleton'

const LandingPage = lazy(() => import('@/landing/LandingPage'))
const ChatLayout = lazy(() => import('@/chat/ChatLayout'))
const ChatPage = lazy(() => import('@/chat/ChatPage'))

const chatPage = (
  <Suspense fallback={<ChatPageSkeleton />}>
    <ChatPage />
  </Suspense>
)

export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <Suspense fallback={<LandingSkeleton />}>
            <LandingPage />
          </Suspense>
        }
      />
      <Route
        path="/chat"
        element={
          <Suspense fallback={<ChatShellSkeleton />}>
            <ChatLayout />
          </Suspense>
        }
      >
        <Route index element={chatPage} />
        <Route path=":chatId" element={chatPage} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
