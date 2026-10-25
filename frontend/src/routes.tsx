import { Navigate, type RouteObject } from 'react-router-dom'
import ChatLayout from '@/chat/ChatLayout'
import ChatPage from '@/chat/ChatPage'
import LandingPage from '@/landing/LandingPage'

export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  {
    path: '/chat',
    element: <ChatLayout />,
    children: [
      { index: true, element: <ChatPage /> },
      { path: ':chatId', element: <ChatPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]
