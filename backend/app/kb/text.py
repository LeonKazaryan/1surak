"""Search terms for Russian text without a stemming library.

The 'simple' full-text config keeps every word form, so «визы» would not find «виза». We cut common
endings and search by prefix instead: «визы» → виз:*, «отели» → отел:*, «детьми» → дет:*.
"""

import re

STOPWORDS = {
    # ru
    "и", "в", "во", "на", "с", "со", "к", "ко", "по", "о", "об", "от", "до", "из", "за", "для", "без", "при",
    "у", "а", "но", "или", "ли", "же", "бы", "не", "ни", "то", "это", "как", "что", "где", "когда", "куда",
    "какой", "какая", "какие", "каких", "какую", "мне", "нам", "нас", "мы", "я", "вы", "вас", "там", "тут",
    "есть", "нужно", "нужна", "нужен", "нужны", "можно", "сейчас", "очень", "все", "всё", "так",
    "еще", "ещё", "уже", "был", "была", "были", "будет", "сколько", "лучше", "хочу", "хотим", "подскажи",
    # en
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are", "do", "does", "how",
    "what", "where", "when", "can", "i", "we", "my", "our", "it", "be", "need", "there",
}  # fmt: skip
WORD = re.compile(r"[\w-]+", re.UNICODE)
CYRILLIC = re.compile(r"[а-яё]")


def stem(word: str) -> str:
    word = word.casefold().replace("ё", "е")
    if CYRILLIC.search(word):
        if len(word) >= 6:  # «детьми» → дет, «Хургаде» → хург
            return word[:-3]
        if len(word) == 5:
            return word[:-2]
        if len(word) == 4:
            return word[:-1]
        return word
    return word[:-1] if len(word) >= 5 and word.endswith("s") else word


def terms(query: str) -> list[str]:
    seen: list[str] = []
    for raw in WORD.findall(query):
        word = raw.strip("-").casefold()
        if len(word) < 2 or word in STOPWORDS or word.isdigit():
            continue
        term = stem(word)
        if len(term) >= 2 and term not in seen:
            seen.append(term)
    return seen


def fts_query(query: str) -> str | None:
    """«виза в Таиланд» → "'виз':* | 'таил':*" for to_tsquery. None when nothing is left to search for."""
    found = terms(query)
    return " | ".join(f"'{t}':*" for t in found) if found else None


def coverage(query: str, text: str, ignore: set[str] = frozenset()) -> float:
    """Share of the query's terms that the text contains: how well a stored entry answers the question.
    `ignore` drops terms every candidate shares anyway, like the place name the search already filtered on."""
    wanted = [t for t in terms(query) if t not in ignore]
    if not wanted:
        return 0.0
    words = {w.casefold().replace("ё", "е") for w in WORD.findall(text)}
    hit = sum(any(w.startswith(t) for w in words) for t in wanted)
    return hit / len(wanted)


def _close(word: str, term: str) -> bool:
    """Prefix match, plus short words that differ only in the ending («еды» and «еда»): stem() leaves words
    under four letters alone. Looser than the search index on purpose: this only ranks sentences."""
    if word.startswith(term):
        return True
    return 3 <= len(term) <= 4 and len(word) <= len(term) + 1 and word[: len(term) - 1] == term[:-1]


SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")


def excerpt(text: str, query: str, limit: int, ignore: set[str] = frozenset()) -> str:
    """The sentences that answer the query, in their original order, within `limit` characters.
    A stored passage can be 1500 characters of a page; the model only needs the part about the question,
    and the rest would ride along in every later call of the turn. Gaps are marked with «…»."""
    if len(text) <= limit:
        return text
    sentences = [s.strip() for s in SENTENCE.split(text) if s.strip()]
    wanted = [t for t in terms(query) if t not in ignore]

    def hits(sentence: str) -> int:
        words = {w.casefold().replace("ё", "е") for w in WORD.findall(sentence)}
        return sum(any(_close(w, t) for w in words) for t in wanted)

    scores = [hits(s) for s in sentences]
    if not any(scores):
        return text[: limit - 1].rstrip() + "…"
    keep: set[int] = set()
    size = 0
    for i in sorted(range(len(sentences)), key=lambda i: (-scores[i], i)):
        if not scores[i]:
            break
        if size + len(sentences[i]) + 2 <= limit:
            keep.add(i)
            size += len(sentences[i]) + 2
    if not keep:  # the best sentence alone is longer than the limit
        best = max(range(len(sentences)), key=lambda i: scores[i])
        return sentences[best][: limit - 1].rstrip() + "…"
    parts: list[str] = []
    previous = -1
    for i in sorted(keep):
        if i > previous + 1:
            parts.append("…")
        parts.append(sentences[i])
        previous = i
    if previous < len(sentences) - 1:
        parts.append("…")
    return " ".join(parts)


def sections(text: str, query: str, limit: int, ignore: set[str] = frozenset(), after: int = 3) -> str:
    """For a whole page: the lines that match the query plus the few lines after each, so a matching
    heading («Еда») brings its section along, in page order, within `limit` characters. The start of the
    page when nothing matches."""
    if len(text) <= limit:
        return text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    wanted = [t for t in terms(query) if t not in ignore]

    def hits(line: str) -> int:
        words = {w.casefold().replace("ё", "е") for w in WORD.findall(line)}
        return sum(any(_close(w, t) for w in words) for t in wanted)

    scores = [hits(line) for line in lines]
    keep: set[int] = set()
    size = 0
    for i in sorted(range(len(lines)), key=lambda i: (-scores[i], i)):
        if not scores[i]:
            break
        for j in range(i, min(i + after + 1, len(lines))):
            if j not in keep and size + len(lines[j]) + 1 <= limit:
                keep.add(j)
                size += len(lines[j]) + 1
    if not keep:
        return text[:limit]
    parts: list[str] = []
    previous = -1
    for i in sorted(keep):
        if i > previous + 1:
            parts.append("…")
        parts.append(lines[i])
        previous = i
    return "\n".join(parts)
