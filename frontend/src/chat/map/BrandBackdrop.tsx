import { useMemo } from 'react'
import { motion } from 'motion/react'
import { cn } from '@/components/ui/utils'
import { bridge, curveThrough, frameAround, landDots, unwrap, viewBox, type LatLon } from './geo'

/** The colours behind a cover without a photo: the site's lime and blue drifting, and the world in dots with
 * the way from home to the destination drawn across it. */
export function BrandBackdrop({ from, to, className }: { from?: LatLon | null; to?: LatLon | null; className?: string }) {
  const { frame, dots, arc } = useMemo(() => {
    const ends = [from, to].filter((p): p is LatLon => Boolean(p))
    const points = ends.length === 2 ? [ends[0], { ...ends[1], lon: unwrap(ends[1].lon, ends[0].lon) }] : ends
    const frame = frameAround(points.length ? points : [{ lat: 35, lon: 40 }], 3.2, 0.45, 70)
    return {
      frame,
      dots: landDots(frame, 2),
      arc: points.length === 2 ? curveThrough(frame, bridge(points[0], points[1], frame.k)) : null,
    }
  }, [from, to])
  const width = (frame.maxLon - frame.minLon) * frame.k
  return (
    <div aria-hidden className={cn('absolute inset-0 overflow-hidden bg-[#f6faf2]', className)}>
      <span className="blob-drift absolute -top-1/3 -left-[10%] h-[150%] w-[55%] rounded-full bg-primary/45 blur-3xl" />
      <span className="blob-drift absolute -right-[12%] -bottom-1/2 h-[150%] w-[55%] rounded-full bg-highlight/15 blur-3xl [animation-delay:-6s] [animation-duration:20s]" />
      <svg viewBox={viewBox(frame)} preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
        <motion.path
          d={dots.d}
          fill="none"
          stroke="#9fb1c4"
          strokeOpacity={0.55}
          strokeWidth={dots.size}
          strokeLinecap="round"
          strokeDasharray={`0 ${dots.gap}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2 }}
        />
        {arc && (
          <motion.path
            d={arc}
            fill="none"
            stroke="var(--highlight)"
            strokeWidth={width / 260}
            strokeLinecap="round"
            strokeDasharray={`${width / 120} ${width / 160}`}
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 0.7 }}
            transition={{ duration: 1.6, delay: 0.4, ease: [0.65, 0, 0.35, 1] }}
          />
        )}
      </svg>
    </div>
  )
}

