"""Search terms for Russian text without a stemming library.

SQLite's unicode61 tokenizer has no Russian stemming, so «визы» would not find «виза». We cut common
endings and search by prefix instead: «визы» → виз*, «отели» → отел*, «детьми» → дет*.
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
    """«виза в Таиланд» → '"виз"* OR "таила"*'. None when nothing is left to search for."""
    found = terms(query)
    return " OR ".join(f'"{t}"*' for t in found) if found else None


def coverage(query: str, text: str, ignore: set[str] = frozenset()) -> float:
    """Share of the query's terms that the text contains: how well a stored entry answers the question.
    `ignore` drops terms every candidate shares anyway, like the place name the search already filtered on."""
    wanted = [t for t in terms(query) if t not in ignore]
    if not wanted:
        return 0.0
    words = {w.casefold().replace("ё", "е") for w in WORD.findall(text)}
    hit = sum(any(w.startswith(t) for w in words) for t in wanted)
    return hit / len(wanted)
