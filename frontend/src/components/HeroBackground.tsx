interface HeroBackgroundProps {
  videoSrc?: string
}

const FALLBACK_GLOW = 'radial-gradient(45% 40% at 50% 60%, rgba(173,239,129,0.28) 0%, rgba(173,239,129,0) 70%)'

export function HeroBackground({ videoSrc }: HeroBackgroundProps) {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden>
      {videoSrc ? (
        <>
          <video
            className="absolute inset-0 h-full w-full object-cover object-center"
            src={videoSrc}
            autoPlay
            muted
            loop
            playsInline
          />
          <div className="absolute inset-0 bg-background/80" />
        </>
      ) : (
        <div data-testid="hero-fallback" className="absolute inset-0" style={{ backgroundImage: FALLBACK_GLOW }} />
      )}
    </div>
  )
}
