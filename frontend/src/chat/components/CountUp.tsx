import { useEffect, useRef } from 'react'
import { animate, motion, useInView, useMotionValue, useReducedMotion, useTransform } from 'motion/react'

const FROM = 0.7

/** A sum that counts up to its value as it comes into view, and glides to a new value when the price moves.
 * Until it is seen (and in a test, or with reduced motion) it simply shows the value. */
export function CountUp({ value, format, delay = 0.4 }: { value: number; format: (n: number) => string; delay?: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const count = useMotionValue(value)
  const text = useTransform(count, format)
  const seen = useInView(ref, { once: true })
  const still = useReducedMotion()
  const counted = useRef(false)
  useEffect(() => {
    if (!seen || still) {
      count.set(value)
      return
    }
    if (!counted.current) count.jump(value * FROM)
    counted.current = true
    const controls = animate(count, value, { duration: 0.9, delay, ease: [0.215, 0.61, 0.355, 1] })
    return () => controls.stop()
  }, [seen, still, value, delay, count])
  return <motion.span ref={ref}>{text}</motion.span>
}
