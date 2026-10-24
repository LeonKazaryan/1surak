import { Link } from 'react-router-dom'
import { cn } from '@/components/ui/utils'
import { LogoMark } from './LogoMark'

interface LogoProps {
  className?: string
}

export function Wordmark({ className }: LogoProps) {
  return (
    <span className={cn('font-brand text-lg font-extrabold max-sm:text-base tracking-[-0.03em] text-foreground', className)}>
      <span className="text-highlight">1</span>surak
    </span>
  )
}

export function Logo({ className }: LogoProps) {
  return (
    <Link to="/" aria-label="1surak" className={cn('flex shrink-0 items-center gap-2.5', className)}>
      <LogoMark className="h-9 w-9 shrink-0" />
      <Wordmark className="max-[370px]:hidden" />
    </Link>
  )
}
