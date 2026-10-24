import { useCallback, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'

const STEP_PX = 24

interface ResizablePanelOptions {
  storageKey: string
  min: number
  max: number
  initial: number
}

interface ResizablePanel {
  width: number
  isResizing: boolean
  startResize: (e: MouseEvent<HTMLDivElement>) => void
  onSeparatorKeyDown: (e: KeyboardEvent<HTMLDivElement>) => void
  reset: () => void
}

function readStoredWidth({ storageKey, min, max, initial }: ResizablePanelOptions): number {
  try {
    const n = Number.parseInt(localStorage.getItem(storageKey) ?? '', 10)
    return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : initial
  } catch {
    return initial
  }
}

/** Width of a right-hand panel resized by dragging (or arrow keys on) its left separator. */
export function useResizablePanel(options: ResizablePanelOptions): ResizablePanel {
  const { storageKey, min, max, initial } = options
  const [width, setWidth] = useState(() => readStoredWidth(options))
  const [isResizing, setIsResizing] = useState(false)
  const widthRef = useRef(width)

  const apply = useCallback(
    (next: number, persist: boolean) => {
      const clamped = Math.min(max, Math.max(min, next))
      widthRef.current = clamped
      setWidth(clamped)
      if (!persist) return
      try {
        localStorage.setItem(storageKey, String(clamped))
      } catch {
        // Storage blocked: width resets on reload.
      }
    },
    [max, min, storageKey],
  )

  const startResize = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      e.preventDefault()
      const startX = e.clientX
      const startW = widthRef.current
      setIsResizing(true)

      const onMove = (ev: globalThis.MouseEvent) => apply(startW - (ev.clientX - startX), false)
      const onUp = () => {
        setIsResizing(false)
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
        document.body.style.removeProperty('cursor')
        document.body.style.removeProperty('user-select')
        apply(widthRef.current, true)
      }

      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    },
    [apply],
  )

  const onSeparatorKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      const moves: Record<string, number> = {
        ArrowLeft: widthRef.current + STEP_PX,
        ArrowRight: widthRef.current - STEP_PX,
        Home: max,
        End: min,
        Enter: initial,
        ' ': initial,
      }
      if (!(e.key in moves)) return
      e.preventDefault()
      apply(moves[e.key], true)
    },
    [apply, initial, max, min],
  )

  const reset = useCallback(() => apply(initial, true), [apply, initial])

  return { width, isResizing, startResize, onSeparatorKeyDown, reset }
}
