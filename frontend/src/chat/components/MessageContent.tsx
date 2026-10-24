import ReactMarkdown, { type Components } from 'react-markdown'

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

interface MessageContentProps {
  text: string
}

export function MessageContent({ text }: MessageContentProps) {
  return (
    <div className="text-[15px] leading-relaxed wrap-break-word text-foreground">
      <ReactMarkdown components={components}>{text}</ReactMarkdown>
    </div>
  )
}
