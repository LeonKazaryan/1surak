import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

const LandingPage = lazy(() => import('@/landing/LandingPage'))
const ChatLayout = lazy(() => import('@/chat/ChatLayout'))
const ChatPage = lazy(() => import('@/chat/ChatPage'))

export function AppRoutes() {
  return (
    <Suspense fallback={<div className="min-h-svh bg-background" />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/chat" element={<ChatLayout />}>
          <Route index element={<ChatPage />} />
          <Route path=":chatId" element={<ChatPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
