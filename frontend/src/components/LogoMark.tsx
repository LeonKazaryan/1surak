import { cn } from '@/components/ui/utils'

interface LogoMarkProps {
  className?: string
}

export function LogoMark({ className = 'h-9 w-9' }: LogoMarkProps) {
  return <img src="/logo.png" alt="" draggable={false} className={cn('object-contain select-none', className)} />
}
