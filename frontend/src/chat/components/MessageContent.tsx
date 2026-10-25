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

// The agent's prompt ends answers with «Источники:» and one source per line: name, date, link.
const SOURCES_HEADING = /\n[ \t]*\**(?:Источники|Sources):?\**[ \t]*\n/i
const MARKDOWN_LINK = /\[([^\]]+)\]\(([^)\s]+)\)/
const WEB_ADDRESS = /https?:\/\/\S+/i

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

/** The answer before the sources, the sources themselves, and any text after the list's first blank line. */
function splitSources(text: string): { body: string; sources: Source[]; tail: string } {
  const heading = SOURCES_HEADING.exec(text)
  if (!heading) return { body: text, sources: [], tail: '' }
  const [list, ...rest] = text.slice(heading.index + heading[0].length).split(/\n\s*\n/)
  const sources = list.split('\n').map(parseSource).filter((s): s is Source => s !== null)
  if (!sources.length) return { body: text, sources: [], tail: '' }
  return { body: text.slice(0, heading.index), sources, tail: rest.join('\n\n') }
}

function SourceList({ sources }: { sources: Source[] }) {
  const chip = 'inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-[12px]'
  return (
    <div className="mt-3">
      <p className="m-0 mb-1.5 text-xs font-semibold tracking-wider text-faint uppercase">Источники</p>
      <ul aria-label="Источники" className="m-0 flex list-none flex-wrap gap-1.5 p-0">
        {sources.map((source, i) => (
          <li key={`${i}-${source.label}`} className="max-w-full min-w-0">
            {source.url ? (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                title={source.url}
                className={`${chip} text-foreground transition-colors hover:border-highlight/30 hover:bg-accent/60`}
              >
                <span className="truncate">{source.label}</span>
                {source.host && source.host !== source.label && <span className="shrink-0 text-faint">{source.host}</span>}
              </a>
            ) : (
              <span className={`${chip} text-muted-foreground`}>
                <span className="truncate">{source.label}</span>
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
      <ReactMarkdown components={components}>{body}</ReactMarkdown>
      {sources.length > 0 && <SourceList sources={sources} />}
      {tail && (
        <div className="mt-3">
          <ReactMarkdown components={components}>{tail}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}
