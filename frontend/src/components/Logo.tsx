import { Link } from 'react-router-dom'
import { cn } from '@/components/ui/utils'
import { LogoMark } from './LogoMark'

interface LogoProps {
  className?: string
}

export function Logo({ className }: LogoProps) {
  return (
    <Link to="/" className={cn('flex shrink-0 items-center gap-2.5', className)}>
      <LogoMark className="h-9 w-9 shrink-0" />
      <span className="text-[15px] font-semibold tracking-tight text-foreground">1surak</span>
    </Link>
  )
}
