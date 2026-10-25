import { useRoutes } from 'react-router-dom'
import { routes } from './routes'

export function AppRoutes() {
  return useRoutes(routes)
}
