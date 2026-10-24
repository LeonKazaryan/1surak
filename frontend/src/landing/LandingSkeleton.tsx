import { LogoMark } from '@/components/LogoMark'
import { Skeleton } from '@/components/ui/skeleton'

const HEADING_WIDTHS = ['w-[min(62%,26rem)]', 'w-[min(96%,40rem)]']
const TEXT_WIDTHS = ['w-[94%]', 'w-[88%]', 'w-[45%]']
const CHIP_WIDTHS = ['w-[187px]', 'w-[174px]', 'w-[178px]']

export function LandingSkeleton() {
  return (
    <>
      <span role="status" className="sr-only">
        Загрузка
      </span>
      <div data-testid="landing-skeleton" aria-hidden className="flex min-h-svh flex-col bg-background">
        <div className="fixed top-3 left-1/2 z-50 flex h-16 w-[92%] max-w-3xl -translate-x-1/2 items-center justify-between rounded-2xl border border-border/70 bg-card px-4 shadow-md">
          <div className="flex items-center gap-2.5">
            <LogoMark className="h-9 w-9" />
            <span className="text-[15px] font-semibold tracking-tight text-foreground">1surak</span>
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="hidden h-9 w-24 rounded-full sm:block" />
            <Skeleton className="h-9 w-9 rounded-lg" />
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-[clamp(1.25rem,4vh,2.75rem)] px-4 py-8">
          <div className="flex w-full flex-col items-center">
            <div className="flex min-h-[2.3em] w-full flex-col items-center gap-[0.1em] text-[clamp(2.1rem,5.4vw,4.5rem)]">
              {HEADING_WIDTHS.map((width) => (
                <Skeleton key={width} className={`h-[1em] rounded-xl ${width}`} />
              ))}
            </div>
            <div className="mt-[clamp(0.75rem,2vh,1.5rem)] flex w-full max-w-xl flex-col items-center gap-[0.625em] text-[clamp(1rem,1.6vw,1.375rem)]">
              {TEXT_WIDTHS.map((width) => (
                <Skeleton key={width} className={`h-[1em] ${width}`} />
              ))}
            </div>
          </div>
          <Skeleton className="h-[62px] w-full max-w-xl rounded-2xl" />
          <div className="flex flex-wrap justify-center gap-2">
            {CHIP_WIDTHS.map((width) => (
              <Skeleton key={width} className={`h-9 rounded-full ${width}`} />
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
