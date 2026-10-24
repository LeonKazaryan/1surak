interface LogoMarkProps {
  className?: string
}

export function LogoMark({ className = 'h-9 w-9' }: LogoMarkProps) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden focusable="false">
      <rect width="40" height="40" rx="11" fill="#0f172a" />
      <path d="M15.2 12.6 20.4 10H22v17.6h3.4V30H14.6v-2.4h4V14.4l-2.7 1.2z" fill="#fff" />
      <circle cx="30.5" cy="10.5" r="3" fill="var(--primary)" />
    </svg>
  )
}
