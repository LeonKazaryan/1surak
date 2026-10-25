import { useCallback, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/components/ui/utils'

interface ScrollRowProps {
  label: string
  children: ReactNode
  className?: string
  rowClassName?: string
}

/** A row of chips that scrolls sideways when it does not fit, fading only the side with more to see. */
export function ScrollRow({ label, children, className, rowClassName }: ScrollRowProps) {
  const row = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ start: false, end: false })

  const measure = useCallback(() => {
    const el = row.current
    if (!el) return
    const hidden = el.scrollWidth - el.clientWidth
    setEdges({ start: el.scrollLeft > 1, end: el.scrollLeft < hidden - 1 })
  }, [])

  useLayoutEffect(() => {
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(row.current!)
    return () => observer.disconnect()
  }, [measure])

  return (
    <div
      ref={row}
      role="group"
      aria-label={label}
      onScroll={measure}
      data-fade-start={edges.start || undefined}
      data-fade-end={edges.end || undefined}
      className={cn('scroll-row overflow-x-auto', className)}
    >
      <div className={cn('mx-auto flex w-max gap-2 px-4 py-1 whitespace-nowrap', rowClassName)}>{children}</div>
    </div>
  )
}
