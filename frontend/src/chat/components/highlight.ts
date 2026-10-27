// The agent's prices and the places on its cards stand out in its text: a rehype plugin that splits text
// nodes into plain text and marked spans (no raw HTML, so nothing the model writes becomes markup).

interface HastNode {
  type: string
  value?: string
  tagName?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
}

export interface TextPlace {
  id: string
  name: string
  countryCode?: string
}

const PRICE = String.raw`(?:от\s)?\d{1,3}(?:[\u00a0 ]\d{3})*(?:[.,]\d+)?\u00a0?(?:₽|₸|€|\$|Br\b|сум\b|сом\b)|[$€]\d[\d\u00a0 ]*\d`
const SKIP = new Set(['a', 'code', 'pre'])

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function highlightPlugin(places: TextPlace[]) {
  const named = places.filter((p) => p.name.length > 2).sort((a, b) => b.name.length - a.name.length)
  const byName = new Map(named.map((p) => [p.name.toLowerCase(), p]))
  const names = named.map((p) => escape(p.name))
  // a place's name counts as a word: «Анталья» but not inside «Антальяскиe»
  const pattern = new RegExp(`(${PRICE})${names.length ? `|(?<![\\p{L}])(${names.join('|')})(?![\\p{L}])` : ''}`, 'giu')

  function split(text: string): HastNode[] {
    const out: HastNode[] = []
    let last = 0
    for (const match of text.matchAll(pattern)) {
      const at = match.index ?? 0
      if (at > last) out.push({ type: 'text', value: text.slice(last, at) })
      const [whole, price, place] = match
      if (price) {
        out.push({ type: 'element', tagName: 'span', properties: { className: ['price-chip'] }, children: [{ type: 'text', value: whole }] })
      } else if (place) {
        const found = byName.get(place.toLowerCase())
        out.push({
          type: 'element',
          tagName: 'span',
          properties: { className: ['place-chip'], dataPlace: found?.id ?? '', dataFlag: found?.countryCode ?? '' },
          children: [{ type: 'text', value: whole }],
        })
      }
      last = at + whole.length
    }
    if (last < text.length) out.push({ type: 'text', value: text.slice(last) })
    return out
  }

  function walk(node: HastNode) {
    if (!node.children || (node.tagName && SKIP.has(node.tagName))) return
    node.children = node.children.flatMap((child) => {
      if (child.type === 'text' && child.value) return split(child.value)
      walk(child)
      return [child]
    })
  }

  return () => (tree: HastNode) => walk(tree)
}
