import ReactMarkdown, { type Components } from 'react-markdown'
import { keepPricesTogether } from '../widgets'

const components: Components = {
  p: ({ children }) => <p className="m-0 mb-3 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="m-0 mb-3 flex list-disc flex-col gap-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="m-0 mb-3 flex list-decimal flex-col gap-1 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  h1: ({ children }) => <h3 className="m-0 mb-2 text-lg font-semibold tracking-tight text-foreground">{children}</h3>,
  h2: ({ children }) => <h3 className="m-0 mb-2 text-base font-semibold tracking-tight text-foreground">{children}</h3>,
  h3: ({ children }) => <h4 className="m-0 mb-1.5 text-sm font-semibold text-foreground">{children}</h4>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-highlight underline-offset-2 hover:underline">
      {children}
    </a>
  ),
  code: ({ children }) => <code className="rounded bg-secondary px-1 py-0.5 text-[12.5px]">{children}</code>,
}

// The agent's prompt ends answers with «Источники:» and one source per line: name, date, link. The model
// sometimes writes them in the sentence instead: «Источники: Aviasales.kz, проверено 26.10.2026, https://…; …».
const SOURCES_HEADING = /\n[ \t]*\**(?:Источники|Sources):?\**[ \t]*\n/i
const SOURCES_INLINE = /(^|\s)\**(?:Источники|Sources)\**:\**[ \t]*/
const MARKDOWN_LINK = /\[([^\]]+)\]\(([^)\s]+)\)/
const WEB_ADDRESS = /https?:\/\/\S+/i
const BARE_ADDRESS = /(\]\()?(https?:\/\/\S+)/gi

interface Source {
  label: string
  url: string | null
  host: string
}

function hostOf(url: string | null): string {
  try {
    return url ? new URL(url).hostname.replace(/^www\./, '') : ''
  } catch {
    return ''
  }
}

/** Drops the punctuation of the sentence around an address, but not a bracket that belongs to it. */
function trimAddress(raw: string): string {
  let url = raw.replace(/[.,;]+$/, '')
  while (url.endsWith(')') && url.split(')').length > url.split('(').length) url = url.slice(0, -1)
  return url
}

function parseSource(line: string): Source | null {
  const text = line.replace(/^\s*(?:[-*•]|\d+\.)\s*/, '').trim()
  if (!text) return null
  const link = text.match(MARKDOWN_LINK)
  const raw = link ? link[2] : text.match(WEB_ADDRESS)?.[0]
  const url = raw && /^https?:\/\//i.test(raw) ? trimAddress(raw) : null
  const named = link ? text.replace(link[0], link[1]) : raw ? text.replace(raw, '') : text
  const host = hostOf(url)
  return { label: named.replace(/[\s,;:·]+$/, '').trim() || host, url, host }
}

/** The answer before the sources, the sources themselves, and any text after the list's first blank line.
 * A list under its own heading goes line by line; one written into the sentence, source by source after «;». */
function splitSources(text: string): { body: string; sources: Source[]; tail: string } {
  const heading = SOURCES_HEADING.exec(text)
  const inline = heading ? null : SOURCES_INLINE.exec(text)
  const found = heading ?? inline
  if (!found) return { body: text, sources: [], tail: '' }
  const [list, ...rest] = text.slice(found.index + found[0].length).split(/\n\s*\n/)
  if (inline && !WEB_ADDRESS.test(list)) return { body: text, sources: [], tail: '' } // «источники» in a sentence
  const items = heading ? list.split('\n') : list.split(/;\s*|\n/)
  const sources = items.map(parseSource).filter((s): s is Source => s !== null)
  if (!sources.length) return { body: text, sources: [], tail: '' }
  const body = text.slice(0, found.index + (inline ? inline[1].length : 0)).trimEnd()
  return { body, sources, tail: rest.join('\n\n') }
}

/** A bare address in the answer becomes a short link with the site's name: the address itself is noise. */
function linkAddresses(text: string): string {
  return text.replace(BARE_ADDRESS, (match, inLink: string | undefined, raw: string) => {
    if (inLink) return match // already a markdown link
    const url = trimAddress(raw)
    const host = hostOf(url)
    return host ? `[${host}](${url})${raw.slice(url.length)}` : match
  })
}

/** The source's name without the date and notes after it: «Aviasales.kz, проверено 26.10.2026» → «Aviasales.kz». */
function shortName(source: Source): string {
  const name = source.label.split(/,\s*/)[0].trim()
  return name.length > 28 ? source.host || name.slice(0, 28) : name || source.host
}

/** A site's mark: its first letter on a colour of its own, so the sources read like a row of logos without
 * loading anyone's images. */
function SiteMark({ host }: { host: string }) {
  const hue = [...host].reduce((sum, ch) => (sum * 31 + ch.charCodeAt(0)) % 360, 7)
  return (
    <span
      aria-hidden
      style={{ backgroundColor: `hsl(${hue} 70% 92%)`, color: `hsl(${hue} 55% 32%)` }}
      className="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full text-[10px] font-bold uppercase"
    >
      {host.charAt(0) || '·'}
    </span>
  )
}

function SourceList({ sources }: { sources: Source[] }) {
  const chip = 'inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-card py-0.5 pr-2.5 pl-0.5 text-[12px]'
  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5">
      <span className="text-[12px] text-faint">Источники</span>
      <ul aria-label="Источники" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {sources.map((source, i) => (
          <li key={`${i}-${source.label}`} className="max-w-full min-w-0">
            {source.url ? (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                title={`${source.label}\n${source.url}`}
                className={`${chip} font-medium text-foreground transition-colors hover:border-highlight/30 hover:bg-accent/60`}
              >
                <SiteMark host={source.host} />
                <span className="truncate">{shortName(source)}</span>
              </a>
            ) : (
              <span title={source.label} className={`${chip} pl-2.5 text-muted-foreground`}>
                <span className="truncate">{shortName(source)}</span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

interface MessageContentProps {
  text: string
}

export function MessageContent({ text }: MessageContentProps) {
  const { body, sources, tail } = splitSources(keepPricesTogether(text))
  return (
    <div className="text-[15px] leading-relaxed wrap-break-word text-foreground">
      <ReactMarkdown components={components}>{linkAddresses(body)}</ReactMarkdown>
      {sources.length > 0 && <SourceList sources={sources} />}
      {tail && (
        <div className="mt-3">
          <ReactMarkdown components={components}>{linkAddresses(tail)}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}
