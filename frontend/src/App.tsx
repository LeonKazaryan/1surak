import { Navigate, Route, Routes } from 'react-router-dom'
import ChatLayout from '@/chat/ChatLayout'
import ChatPage from '@/chat/ChatPage'
import LandingPage from '@/landing/LandingPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/chat" element={<ChatLayout />}>
        <Route index element={<ChatPage />} />
        <Route path=":chatId" element={<ChatPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
