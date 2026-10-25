import { useId, useState, type ReactElement } from 'react'
import { cn } from '@/components/ui/utils'
import type { Photo, TripKind } from '@/types/api'

interface TripArtProps {
  kind: TripKind
  /** Varies the scene (sun position, skyline) so neighbouring cards differ. */
  seed?: string
  photo?: Photo | null
  /** Freezes the waves, clouds and snow: for many scenes on screen at once. */
  still?: boolean
  className?: string
}

const W = 320
const H = 160

function hash(text: string): number {
  let h = 2166136261
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619)
  return (h >>> 0) / 4294967295
}

/** A wave line twice the scene width, so sliding it left by one width loops seamlessly. */
function wavePath(y: number, amplitude: number, length: number): string {
  let d = `M0 ${y}`
  for (let x = 0; x < W * 2; x += length) {
    d += ` q${length / 4} ${-amplitude} ${length / 2} 0 t${length / 2} 0`
  }
  return `${d} V${H} H0 Z`
}

function Cloud({ x, y, scale = 1, className }: { x: number; y: number; scale?: number; className?: string }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} className={className}>
      <ellipse cx="0" cy="0" rx="22" ry="9" fill="white" opacity="0.9" />
      <ellipse cx="12" cy="-6" rx="13" ry="10" fill="white" opacity="0.9" />
      <ellipse cx="-9" cy="-4" rx="10" ry="8" fill="white" opacity="0.9" />
    </g>
  )
}

function Sea({ id, r }: { id: string; r: number }) {
  const sunX = 60 + r * 200
  return (
    <>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#d8f0ff" />
          <stop offset="1" stopColor="#a5dcff" />
        </linearGradient>
        <linearGradient id={`${id}-sea`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3b9cff" />
          <stop offset="1" stopColor="#0a40d1" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}-sky)`} />
      <circle cx={sunX} cy="50" r="34" fill="#fff6c4" opacity="0.45" />
      <circle cx={sunX} cy="50" r="18" fill="#fff1a6" />
      <g className="art-drift-slow">
        <Cloud x={40} y={36} scale={0.8} />
        <Cloud x={230} y={28} scale={0.6} />
        <Cloud x={360} y={36} scale={0.8} />
        <Cloud x={550} y={28} scale={0.6} />
      </g>
      <path d={wavePath(102, 3, 40)} fill={`url(#${id}-sea)`} opacity="0.55" className="art-drift" />
      <path d={wavePath(110, 4, 56)} fill={`url(#${id}-sea)`} className="art-drift-reverse" />
      <path d={`M${W - 120} ${H} q40 -34 120 -30 V${H} Z`} fill="#f6e3b4" />
      <path d={`M${W - 52} ${H - 28} q-4 -26 6 -50`} stroke="#7a5a35" strokeWidth="4" fill="none" strokeLinecap="round" />
      <g transform={`translate(${W - 46} ${H - 80})`} fill="#7fd14d">
        <path d="M0 2 q-22 -6 -34 10 q16 -8 34 -6z" />
        <path d="M0 2 q22 -8 34 8 q-16 -6 -34 -4z" />
        <path d="M0 2 q-10 -20 -30 -18 q16 4 30 18z" />
        <path d="M0 2 q12 -20 30 -16 q-16 4 -30 16z" />
      </g>
    </>
  )
}

function Mountains({ id, r }: { id: string; r: number }) {
  const shift = (r - 0.5) * 60
  return (
    <>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#d6efff" />
          <stop offset="1" stopColor="#effbe6" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}-sky)`} />
      <circle cx={250 - shift} cy="40" r="14" fill="#fff1a6" />
      <g className="art-drift-slow">
        <Cloud x={70} y={34} scale={0.7} />
        <Cloud x={390} y={34} scale={0.7} />
      </g>
      <path d={`M-10 ${H} L${70 + shift} 58 L${130 + shift} 100 L${190 + shift} 48 L${290 + shift} 118 L${W + 10} 84 V${H} Z`} fill="#9cc3d9" />
      <path d={`M-10 ${H} L${40 + shift} 92 L${110 + shift} 60 L${180 + shift} 110 L${250 + shift} 66 L${W + 10} 120 V${H} Z`} fill="#3d6f8e" />
      <path d={`M${110 + shift} 60 L${96 + shift} 72 L${104 + shift} 70 L${110 + shift} 76 L${117 + shift} 69 L${124 + shift} 72 Z`} fill="white" />
      <path d={`M${250 + shift} 66 L${236 + shift} 78 L${244 + shift} 76 L${250 + shift} 82 L${257 + shift} 75 L${264 + shift} 78 Z`} fill="white" />
      <path d={`M-10 ${H} Q80 120 170 138 T${W + 10} 128 V${H} Z`} fill="#adef81" />
    </>
  )
}

function City({ id, r }: { id: string; r: number }) {
  const towers = Array.from({ length: 11 }, (_, i) => {
    const h = 40 + hash(`${r}-${i}`) * 62
    return { x: i * 30 - 6, w: 22 + (i % 3) * 4, h }
  })
  return (
    <>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#dbe4ff" />
          <stop offset="1" stopColor="#ffe6d5" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}-sky)`} />
      <circle cx={70 + r * 180} cy="46" r="16" fill="#ffd9a8" />
      {towers.map((t, i) => (
        <rect key={`b${i}`} x={t.x + 14} y={H - t.h - 22} width={t.w} height={t.h + 22} fill="#8aa5f5" opacity="0.7" />
      ))}
      {towers.map((t, i) => (
        <g key={`f${i}`}>
          <rect x={t.x} y={H - t.h} width={t.w} height={t.h} rx="2" fill="#0a40d1" />
          {Array.from({ length: Math.floor(t.h / 14) }, (_, row) =>
            [0, 1].map((col) =>
              hash(`${i}-${row}-${col}-${r}`) > 0.45 ? (
                <rect key={`${row}-${col}`} x={t.x + 5 + col * (t.w / 2 - 2)} y={H - t.h + 7 + row * 14} width="4" height="5" rx="1" fill="#adef81" className={(row + col + i) % 4 === 0 ? 'art-twinkle' : undefined} />
              ) : null,
            ),
          )}
        </g>
      ))}
    </>
  )
}

function Nature({ id, r }: { id: string; r: number }) {
  const trees = [30, 58, 210, 236, 262].map((x, i) => ({ x: x + (r - 0.5) * 30, s: 0.8 + ((i * 7) % 5) / 10 }))
  return (
    <>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#d9f3ff" />
          <stop offset="1" stopColor="#effbe6" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}-sky)`} />
      <circle cx={160 + (r - 0.5) * 140} cy="44" r="16" fill="#fff1a6" />
      <g className="art-drift-slow">
        <Cloud x={60} y={40} scale={0.7} />
        <Cloud x={220} y={30} scale={0.5} />
        <Cloud x={380} y={40} scale={0.7} />
        <Cloud x={540} y={30} scale={0.5} />
      </g>
      <path d={`M-10 ${H} Q60 92 150 112 T${W + 10} 100 V${H} Z`} fill="#c8f2a6" />
      <path d={`M-10 ${H} Q100 112 190 128 T${W + 10} 120 V${H} Z`} fill="#7fd14d" />
      {trees.map((t, i) => (
        <g key={i} transform={`translate(${t.x} ${126 - i * 2}) scale(${t.s})`}>
          <rect x="-2" y="0" width="4" height="10" fill="#6b4b2a" />
          <path d="M0 -30 L13 2 H-13 Z" fill="#2f7a3a" />
          <path d="M0 -40 L10 -14 H-10 Z" fill="#3d9447" />
        </g>
      ))}
    </>
  )
}

function Ski({ id, r }: { id: string; r: number }) {
  const flakes = Array.from({ length: 18 }, (_, i) => ({
    x: hash(`fx${i}${r}`) * W,
    y: hash(`fy${i}${r}`) * H * 0.7,
    s: 1 + hash(`fs${i}`) * 1.6,
  }))
  return (
    <>
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#cfe4ff" />
          <stop offset="1" stopColor="#f3f8ff" />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}-sky)`} />
      <path d={`M-10 ${H} L90 50 L150 96 L220 40 L${W + 10} 110 V${H} Z`} fill="#b7cdee" />
      <path d={`M-10 ${H} L90 50 L150 96 L220 40 L${W + 10} 110 V${H} Z`} fill="white" opacity="0.55" />
      <path d={`M90 50 L60 84 L82 78 L96 88 L112 66 Z`} fill="#8eaad6" opacity="0.6" />
      <path d={`M-10 ${H} Q120 104 200 126 T${W + 10} 132 V${H} Z`} fill="white" />
      <path d={`M60 ${H} Q130 122 230 112`} stroke="#0a40d1" strokeOpacity="0.25" strokeWidth="2" strokeDasharray="4 5" fill="none" />
      <g className="art-snow">
        {flakes.map((f, i) => (
          <circle key={i} cx={f.x} cy={f.y} r={f.s} fill="white" />
        ))}
      </g>
    </>
  )
}

const SCENES: Record<TripKind, (props: { id: string; r: number }) => ReactElement> = {
  sea: Sea,
  mountains: Mountains,
  city: City,
  nature: Nature,
  ski: Ski,
}

/** A real photo when there is one; the illustration for its kind of trip when there is none or it fails to load. */
export function TripArt({ kind, seed = '', photo, still, className }: TripArtProps) {
  const id = useId().replace(/:/g, '')
  const [broken, setBroken] = useState<string | null>(null)
  const image = photo?.url
  if (image && broken !== image) {
    return (
      <img
        src={image}
        alt=""
        title={`Фото: ${photo.author}, ${photo.license}`}
        draggable={false}
        loading="lazy"
        onError={() => setBroken(image)}
        className={cn('h-full w-full bg-(--skeleton) object-cover', className)}
      />
    )
  }
  const Scene = SCENES[kind] ?? Sea
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
      className={cn('h-full w-full overflow-hidden', still && 'art-still', className)}
    >
      <Scene id={id} r={hash(seed || kind)} />
    </svg>
  )
}
