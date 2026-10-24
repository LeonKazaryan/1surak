export interface TextPump {
  push: (chunk: string) => void
  stop: () => void
  text: () => string
}

function charsThisFrame(behind: number): number {
  if (behind <= 4) return 2
  if (behind <= 40) return 12
  if (behind <= 150) return 24
  if (behind <= 400) return 40
  return 60
}

/** Reveals streamed text a few characters per animation frame, catching up faster when far behind. */
export function createTextPump(onShow: (text: string) => void): TextPump {
  let target = ''
  let shown = 0
  let frame: number | null = null

  const tick = () => {
    frame = null
    shown = Math.min(target.length, shown + charsThisFrame(target.length - shown))
    onShow(target.slice(0, shown))
    if (shown < target.length) frame = requestAnimationFrame(tick)
  }

  return {
    push(chunk) {
      target += chunk
      if (frame === null) frame = requestAnimationFrame(tick)
    },
    stop() {
      if (frame !== null) cancelAnimationFrame(frame)
      frame = null
    },
    text: () => target,
  }
}
