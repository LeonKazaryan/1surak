import { CheckIcon, MinusIcon, XMarkIcon } from '@heroicons/react/20/solid'
import type { HotelEvidence } from '@/types/api'

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)
const WEB_PAGE = /^https?:\/\//i
const SAID: Record<HotelEvidence['verdict'], string> = { yes: '', no: 'нет', unknown: 'не нашёл подтверждения' }

function SourceLink({ e }: { e: HotelEvidence }) {
  if (!e.source) return null
  return e.source_url && WEB_PAGE.test(e.source_url) ? (
    <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="text-highlight underline-offset-2 hover:underline">
      {e.source}
    </a>
  ) : (
    <span>{e.source}</span>
  )
}

/** The guest's wishes on the picked hotel: each confirmed one with the source's own words and a link to it. */
export function WishProof({ evidence }: { evidence?: HotelEvidence[] }) {
  if (!evidence?.length) return null
  return (
    <ul aria-label="Ваши пожелания" className="m-0 flex list-none flex-col gap-2.5 rounded-xl bg-inset p-3 text-[13px]">
      {evidence.map((e, i) => (
        <li key={i} className="flex items-start gap-2 leading-snug">
          {e.verdict === 'yes' ? (
            <CheckIcon aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-[#4c9a2a]" />
          ) : e.verdict === 'no' ? (
            <XMarkIcon aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <MinusIcon aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-faint" />
          )}
          <div className="min-w-0">
            <p className="m-0 text-foreground">
              <span className="font-medium">{capital(e.wish)}</span>
              {(e.verdict !== 'yes' || e.note) && (
                <span className="text-muted-foreground">
                  <span aria-hidden> · </span>
                  <span>{e.verdict === 'yes' ? e.note : SAID[e.verdict]}</span>
                </span>
              )}
            </p>
            {e.verdict !== 'unknown' && e.quote && (
              <p className="m-0 mt-0.5 text-[12px] text-muted-foreground">
                <span>{`«${e.quote}»`}</span> <SourceLink e={e} />
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

/** The same in short, for a hotel among others: the confirmed wishes as chips, the quote on hover. */
export function WishChips({ evidence }: { evidence?: HotelEvidence[] }) {
  const confirmed = evidence?.filter((e) => e.verdict === 'yes') ?? []
  const denied = evidence?.filter((e) => e.verdict === 'no') ?? []
  const open = evidence?.filter((e) => e.verdict === 'unknown') ?? []
  if (!confirmed.length && !denied.length && !open.length) return null
  return (
    <div className="flex flex-col gap-1.5">
      {confirmed.length > 0 && (
        <ul aria-label="Подтверждено" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
          {confirmed.map((e, i) => (
            <li key={i} className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-[12px] font-medium text-foreground">
              <CheckIcon aria-hidden className="h-3.5 w-3.5 text-[#4c9a2a]" />
              <span title={[e.quote && `«${e.quote}»`, e.source].filter(Boolean).join(', ')}>{e.wish}</span>
            </li>
          ))}
        </ul>
      )}
      {denied.length > 0 && <p className="m-0 text-[12px] text-muted-foreground">{`Нет: ${denied.map((e) => e.wish).join(', ')}`}</p>}
      {open.length > 0 && (
        <p className="m-0 text-[12px] text-muted-foreground">{`Не подтверждено: ${open.map((e) => e.wish).join(', ')}`}</p>
      )}
    </div>
  )
}
