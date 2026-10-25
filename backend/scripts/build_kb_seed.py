"""Builds the committed knowledge base seed from Wikivoyage. Run on a dev machine, never in the container:

    cd backend && python -m scripts.build_kb_seed

For every catalogue place: ru Wikivoyage sections mapped to topics, with the en section when the ru one
is thin. Passages keep their source URL and revision id (CC BY-SA 4.0, see app/kb/seed/NOTICE.md).
"""

import json
import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import quote

from app.catalog.catalog import load_catalog
from app.kb.seed import SEED_PATH
from scripts.build_catalog_seed import get_json

TOPICS_RU = {
    "Понять": "guide",
    "Как добраться": "transport",
    "Транспорт": "transport",
    "Как передвигаться": "transport",
    "Достопримечательности": "tip",
    "Чем заняться": "tip",
    "Пляжи": "tip",
    "Еда": "food",
    "Безопасность": "safety",
    "Меры предосторожности": "safety",
    "Здоровье": "safety",
}
TOPICS_EN = {
    "Understand": "guide",
    "Get in": "transport",
    "Get around": "transport",
    "See": "tip",
    "Do": "tip",
    "Eat": "food",
    "Stay safe": "safety",
    "Stay healthy": "safety",
}
SECTION_TITLES_RU = {
    "guide": "Понять",
    "transport": "Как добраться",
    "tip": "Чем заняться",
    "food": "Еда",
    "safety": "Безопасность",
}
THIN_CHARS = 300
CHUNK_CHARS = 1300
MAX_CHUNKS_PER_TOPIC = 4
KEEP_DAYS = 180
SKIP_CLASSES = {"mw-editsection", "reference", "noprint", "mw-references-wrap", "thumb", "metadata", "navbox"}
BLOCKS = {"p", "li", "h2", "h3", "h4", "div", "dd", "dt", "tr", "br", "table"}
PAUSE_S = 0.3


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0
        self.stack: list[bool] = []

    def handle_starttag(self, tag, attrs):
        classes = set((dict(attrs).get("class") or "").split())
        skip = tag in ("style", "script", "sup") or bool(classes & SKIP_CLASSES)
        if tag not in ("br", "img", "hr", "wbr", "input", "meta", "link"):
            self.stack.append(skip)
            self.skip_depth += skip
        if tag in BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("br", "img", "hr", "wbr", "input", "meta", "link"):
            return
        if self.stack:
            self.skip_depth -= self.stack.pop()
        if tag in BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def html_to_paragraphs(html: str) -> list[str]:
    parser = TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    paragraphs = [re.sub(r"[ \t\xa0]+", " ", p).strip() for p in text.split("\n")]
    return [p for p in paragraphs if len(p) > 25 and not p.startswith(("Карта", "Map of"))]


def chunks(paragraphs: list[str]) -> list[str]:
    result, current = [], ""
    for p in paragraphs:
        if current and len(current) + len(p) > CHUNK_CHARS:
            result.append(current)
            current = ""
        current = f"{current} {p}".strip() if current else p[:CHUNK_CHARS]
    if current:
        result.append(current)
    return result


H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)


def sections(api: str, page: str, mapping: dict[str, str]) -> tuple[int, dict[str, list[str]]]:
    """One request per page; the HTML is split on top-level headings, which keep their subsections."""
    data = get_json(
        api,
        {"action": "parse", "page": page, "prop": "text|revid", "format": "json"},
        cache=True,
        pause_s=PAUSE_S,
    )
    if "error" in data:
        return 0, {}
    html = data["parse"]["text"]["*"]
    heads = list(H2.finditer(html))
    found: dict[str, list[str]] = {}
    for i, head in enumerate(heads):
        title = re.sub(r"<[^>]+>", "", head.group(1)).strip()
        topic = mapping.get(title)
        if topic is None:
            continue
        body = html[head.end() : heads[i + 1].start() if i + 1 < len(heads) else len(html)]
        found.setdefault(topic, []).extend(html_to_paragraphs(body))
    return data["parse"]["revid"], found


def main() -> None:
    catalog = load_catalog()
    fetched_at = datetime.now(UTC).replace(microsecond=0)
    qids = [p.qid for p in catalog.places]
    links: dict[str, dict] = {}
    for start in range(0, len(qids), 50):
        data = get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbgetentities",
                "ids": "|".join(qids[start : start + 50]),
                "props": "sitelinks",
                "sitefilter": "ruwikivoyage|enwikivoyage",
                "format": "json",
            },
            cache=True,
            pause_s=PAUSE_S,
        )
        links.update(
            {
                q: {k: v["title"] for k, v in e.get("sitelinks", {}).items()}
                for q, e in data["entities"].items()
            }
        )

    entries: list[dict] = []
    for place in catalog.places:
        titles = links.get(place.qid, {})
        ru_title, en_title = titles.get("ruwikivoyage"), titles.get("enwikivoyage")
        ru_rev, ru = (
            sections("https://ru.wikivoyage.org/w/api.php", ru_title, TOPICS_RU) if ru_title else (0, {})
        )
        en_rev, en = (
            sections("https://en.wikivoyage.org/w/api.php", en_title, TOPICS_EN) if en_title else (0, {})
        )
        counts = []
        for topic in ("guide", "tip", "transport", "food", "safety"):
            ru_paras = ru.get(topic, [])
            if sum(map(len, ru_paras)) >= THIN_CHARS:
                lang, paras, title, rev, host = "ru", ru_paras, ru_title, ru_rev, "ru.wikivoyage.org"
            elif en.get(topic):
                lang, paras, title, rev, host = "en", en[topic], en_title, en_rev, "en.wikivoyage.org"
            else:
                continue
            label = SECTION_TITLES_RU[topic]
            for i, text in enumerate(chunks(paras)[:MAX_CHUNKS_PER_TOPIC]):
                entries.append(
                    {
                        "text": f"{place.name}. {label}: {text}",
                        "topic": topic,
                        "kind": "guide",
                        "source_url": f"https://{host}/w/index.php?title={quote(title)}&oldid={rev}",
                        "source_title": f"Wikivoyage ({lang}): {title}",
                        "place_id": place.id,
                        "country": place.country.code,
                        "lang": lang,
                        "attributes": {"licence": "CC BY-SA 4.0", "revid": rev, "part": i + 1},
                        "fetched_at": fetched_at.isoformat(),
                        "valid_until": (fetched_at + timedelta(days=KEEP_DAYS)).isoformat(),
                    }
                )
            counts.append(f"{topic}:{lang}")
        print(f"{place.id:16} ru={ru_title!s:28} en={en_title!s:24} {' '.join(counts)}", flush=True)

    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "about": "Passages adapted from Wikivoyage, © its contributors, CC BY-SA 4.0. See NOTICE.md.",
        "entries": entries,
    }
    SEED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} passages to {SEED_PATH}")


if __name__ == "__main__":
    main()
