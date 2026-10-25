"""Builds the committed travel guide seed (sights, food, dishes, photos) from Wikivoyage and Wikimedia Commons.

    cd backend && .venv/bin/python -m scripts.build_guide_seed

Text is CC BY-SA 4.0 and partly machine-translated; each photo keeps its own licence (see app/plan/seed/NOTICE.md).
"""

import hashlib
import html
import json
import math
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

USER_AGENT = "1surak-hackathon/0.1 (https://github.com/ostrovok-hackathon-2026/beshparmak)"
BACKEND_DIR = Path(__file__).resolve().parent.parent
PLACES_PATH = BACKEND_DIR / "app/catalog/curated/places.json"
SEED_PATH = BACKEND_DIR / "app/plan/seed/guide.json"
CACHE_DIR = BACKEND_DIR / ".cache/build_guide_seed"
ENV_PATH = BACKEND_DIR.parent / ".env"
RU_API = "https://ru.wikivoyage.org/w/api.php"
EN_API = "https://en.wikivoyage.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
PAUSE_S = 0.3
COMMONS_BATCH = 15  # longer batches overflow the GET URL (HTTP 414)
ABOUT = (
    "Sights, food spots and photos adapted from Wikivoyage and Wikimedia Commons, © their contributors. "
    "Text CC BY-SA 4.0; each photo keeps its own author and licence. See NOTICE.md."
)
SUMMARY_MAX = 260
FOOD_INTRO_MAX = 400
SIGHT_TYPES = ("see", "do", "vicinity")
FOOD_TYPES = ("eat", "drink")
MAX_SIGHTS = 12
MAX_FOOD = 8
THIN_SIGHTS = 5
THIN_FOOD = 3
VICINITY_KM = 80
LISTING_KM = 40
PLACE_PHOTO_WIDTH = 1280
LISTING_PHOTO_WIDTH = 640
SECTION_KINDS = {
    "Достопримечательности": "see",
    "Чем заняться": "do",
    "Еда": "eat",
    "Напитки": "drink",
    "See": "see",
    "Do": "do",
    "Eat": "eat",
    "Drink": "drink",
}
# Catalogue titles that do not match the ru article name (verified with the ru opensearch API).
RU_TITLE_OVERRIDES = {"sharm": "Шарм-эль-Шейх"}
# English article for places without a ru article, tried only when ru is missing.
EN_TITLES_WITHOUT_RU = {
    "abu_dhabi": "Abu Dhabi",
    "ras_al_khaimah": "Ras Al Khaimah",
    "sanya": "Sanya",
    "varadero": "Varadero",
    "monastir": "Monastir",
    "zanzibar": "Zanzibar",
    "muscat": "Muscat",
    "seychelles": "Mahé",
    "goa": "Calangute",
    "baikal": "Listvyanka",
    "sharm": "Sharm el-Sheikh",
}
OTA_HOSTS = ("booking.com", "ostrovok", "tripadvisor", "tutu", "travel.yandex", "airbnb", "agoda", "expedia")
FREE_LICENCE = re.compile(r"^(CC BY(-SA)? \d(\.\d)?|CC0|Public domain)")
THUMB_HOST = re.compile(r"^https://thumb\.wikimedia\.org/")
UPLOAD_HOST = "https://upload.wikimedia.org/"  # same thumbnail path, the host the seed contract names
FILE_PAGE = "https://commons.wikimedia.org/wiki/File:"
OPENERS = ("{{", "[[")
CLOSERS = ("}}", "]]")
NAMED_PARAM = re.compile(r"^\s*[\w ]+$")
HEADING = re.compile(r"^==([^=\n].*?)==\s*$", re.MULTILINE)
REDIRECT = re.compile(r"^\s*#\S+\s*\[\[([^\]|#]+)")
FILE_PREFIX = re.compile(r"^\s*(?:Файл|File|Image|Изображение):", re.IGNORECASE)
ARTICLE_FILE = re.compile(r"\[\[(?:Файл|File|Image|Изображение):([^|\]]+)")
QUOTED = re.compile(r"(«[^»]*»|\"[^\"]*\")")
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
TRANSLATE_PROMPT = (
    "You translate one travel guide listing description from English into Russian. "
    "Answer with one or two plain Russian sentences and nothing else. "
    "Translate only what the text says. Do not add facts, prices, opinions or examples. "
    "Do not use dashes as punctuation."
)
DISH_PROMPT = (
    "You extract dishes from a Russian travel guide passage about local cuisine. "
    "Use only dishes named in the passage, written as they appear there. "
    "For each dish give a short Russian note taken from the passage only. "
    "If the passage names no dishes, return an empty list. "
    'Answer with JSON only: {"dishes": [{"name": "...", "note": "..."}]}.'
)


@dataclass(frozen=True)
class Article:
    lang: str
    url: str
    geo: tuple[float, float] | None
    listings: tuple[dict, ...]
    images: tuple[str, ...]
    food_intro: str | None
    langlinks: dict[str, str]
    qid: str | None


@dataclass(frozen=True)
class Photos:
    place: dict
    listing: dict
    p18: dict


def batches(items: list, size: int) -> Iterator[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def cached_json(key: object, fetch: Callable[[], dict]) -> dict:
    name = hashlib.sha256(json.dumps(key, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    path = CACHE_DIR / f"{name}.json"
    if not path.exists():
        data = fetch()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        time.sleep(PAUSE_S)
    return json.loads(path.read_text(encoding="utf-8"))


def http_get(url: str, params: dict) -> dict:
    for attempt in range(5):
        response = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
        if response.status_code not in (429, 500, 502, 503):
            response.raise_for_status()
            return response.json()
        time.sleep(60 if response.status_code == 429 else 5 * (attempt + 1))
    raise RuntimeError(f"{url} kept failing after retries")


def get_json(url: str, params: dict) -> dict:
    return cached_json([url, params], lambda: http_get(url, params))


# Wikitext


def split_top(text: str, sep: str) -> list[str]:
    """Splits on `sep` outside nested {{ }} and [[ ]]."""
    parts, buf, depth, i = [], "", 0, 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair in OPENERS or pair in CLOSERS:
            depth = max(0, depth + (1 if pair in OPENERS else -1))
            buf += pair
            i += 2
        elif text[i] == sep and depth == 0:
            parts.append(buf)
            buf = ""
            i += 1
        else:
            buf += text[i]
            i += 1
    return [*parts, buf]


def matching_end(text: str, start: int) -> int | None:
    depth, i = 0, start
    while i < len(text) - 1:
        pair = text[i : i + 2]
        if pair == "{{":
            depth += 1
            i += 2
        elif pair == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return None


def template_spans(text: str) -> list[tuple[int, int]]:
    spans, i = [], 0
    while (start := text.find("{{", i)) != -1:
        end = matching_end(text, start)
        if end is None:
            break
        spans.append((start, end))
        i = end
    return spans


def named_params(args: list[str]) -> dict[str, str]:
    named = {}
    for arg in args:
        key, sep, value = arg.partition("=")
        if sep and NAMED_PARAM.match(key):
            named[key.strip().lower()] = value.strip()
    return named


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def wikidata_id(value: str) -> str | None:
    match = re.search(r"Q\d+", value)
    return match.group(0) if match else None


def render_hours(args: list[str]) -> str:
    """{{hours|day_from|day_to|h_from|m_from|h_to|m_to}} as plain text, e.g. "8:00–17:00"."""
    d_from, d_to, h_from, m_from, h_to, m_to = ([*args] + [""] * 6)[:6]
    if not (h_from.isdigit() and h_to.isdigit()):
        return ""
    days = f"{d_from}–{d_to}" if d_from and d_to else (d_from or d_to)
    span = f"{h_from}:{m_from or '00'}–{h_to}:{m_to or '00'}"
    return f"{days} {span}".strip()


def render_template(body: str) -> str:
    parts = split_top(body, "|")
    name = parts[0].strip().lower()
    if name == "hours":
        return render_hours([p.strip() for p in parts[1:]])
    if name == "lang" and len(parts) > 2:
        return render(parts[-1])
    return ""


def render(text: str) -> str:
    """Wikitext to plain text. Unknown templates, references and file embeds are dropped."""
    pieces, pos = [], 0
    for start, end in template_spans(text):
        pieces += [text[pos:start], render_template(text[start + 2 : end - 2])]
        pos = end
    flat = "".join([*pieces, text[pos:]])
    flat = re.sub(r"\[\[(?:Файл|File|Image|Изображение):[^\]]*\]\]", "", flat)
    flat = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", flat)
    flat = re.sub(r"\[https?://\S+\s*([^\]]*)\]", r"\1", flat)
    flat = re.sub(r"<!--.*?-->|<ref[^>]*>.*?</ref>|<[^>]+>", " ", flat, flags=re.DOTALL)
    flat = flat.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", html.unescape(flat)).strip()


def strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def section(text: str, title: str) -> str:
    heads = list(HEADING.finditer(text))
    for i, head in enumerate(heads):
        if head.group(1).strip() == title:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            return text[head.end() : end]
    return ""


def food_paragraph(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("{", "*", "|", "=", "<", "#")):
            continue
        plain = render(stripped)
        if len(plain) >= 40:
            return plain
    return None


def find_geo(bodies: list[str]) -> tuple[float, float] | None:
    for body in bodies:
        parts = split_top(body, "|")
        if parts[0].strip().lower() == "geo" and len(parts) >= 3:
            lat, lon = to_float(parts[1].strip()), to_float(parts[2].strip())
            if lat is not None and lon is not None:
                return lat, lon
    return None


def citybar_images(bodies: list[str]) -> list[str]:
    images = []
    for body in bodies:
        parts = split_top(body, "|")
        if parts[0].strip().lower() in ("citybar", "quickbar"):
            image = named_params(parts[1:]).get("image", "")
            images.append(image)
    return [image for image in images if image]


def parse_listing(body: str, lang: str, url: str, section_kind: str | None) -> dict | None:
    parts = split_top(body, "|")
    template = parts[0].strip().lower()
    named = named_params(parts[1:])
    if template == "listing":
        kind = named.get("type", "").lower() or section_kind or ""
    else:
        kind = template
    if kind not in SIGHT_TYPES + FOOD_TYPES:
        return None
    name = render(named.get("name", ""))
    if not name:
        return None
    return {
        "type": kind,
        "name": name,
        "alt": render(named.get("alt", "")) or None,
        "lat": to_float(named.get("lat", "")),
        "lon": to_float(named.get("long", named.get("lon", ""))),
        "wikidata": wikidata_id(named.get("wdid") or named.get("wikidata", "")),
        "star": named.get("star", "").lower() in ("yes", "да", "1", "true"),
        "hours": render(named.get("hours", "")) or None,
        "price": render(named.get("price", "")) or None,
        "address": render(named.get("address", "")) or None,
        "url": named.get("url", ""),
        "image": named.get("image", ""),
        "description": render(named.get("description") or named.get("content", "")),
        "lang": lang,
        "source_url": url,
    }


def section_kind_at(text: str, pos: int) -> str | None:
    """Listing type implied by the level-2 heading above `pos`, for untyped en {{listing}} templates."""
    titles = [(head.start(), head.group(1).strip()) for head in HEADING.finditer(text) if head.start() < pos]
    return SECTION_KINDS.get(titles[-1][1]) if titles else None


def build_article(lang: str, url: str, parse: dict, qid: str | None) -> Article:
    text = parse["wikitext"]
    spans = template_spans(text)
    bodies = [text[start + 2 : end - 2] for start, end in spans]
    listings = tuple(
        item
        for item in (
            parse_listing(body, lang, url, section_kind_at(text, start))
            for body, (start, _) in zip(bodies, spans, strict=True)
        )
        if item
    )
    images = tuple(name.strip() for name in [*citybar_images(bodies), *ARTICLE_FILE.findall(text)])
    intro = food_paragraph(section(text, "Еда")) if lang == "ru" else None
    langlinks = {link["lang"]: link["title"] for link in parse.get("langlinks", [])}
    return Article(
        lang, url, find_geo(bodies), listings, tuple(n for n in images if n), intro, langlinks, qid
    )


# Wikivoyage and Wikidata fetching


def fetch_parse(api: str, title: str) -> dict | None:
    data = get_json(
        api,
        {
            "action": "parse",
            "page": title,
            "prop": "wikitext|langlinks",
            "format": "json",
            "formatversion": "2",
        },
    )
    return None if "error" in data else data["parse"]


def wikibase_item(api: str, title: str) -> str | None:
    data = get_json(
        api, {"action": "query", "titles": title, "prop": "pageprops", "format": "json", "formatversion": "2"}
    )
    pages = data.get("query", {}).get("pages", [])
    return pages[0].get("pageprops", {}).get("wikibase_item") if pages else None


def fetch_article(lang: str, title: str) -> Article | None:
    api = RU_API if lang == "ru" else EN_API
    parse = fetch_parse(api, title)
    target = REDIRECT.match(parse["wikitext"]) if parse else None
    if target:
        parse = fetch_parse(api, target.group(1).strip())
    if parse is None:
        return None
    qid = wikibase_item(api, parse["title"]) if lang == "ru" else None
    url = f"https://{lang}.wikivoyage.org/wiki/{parse['title'].replace(' ', '_')}"
    return build_article(lang, url, parse, qid)


def needs_fallback(ru: Article | None) -> bool:
    if ru is None:
        return True
    sights = sum(1 for item in ru.listings if item["type"] in ("see", "do"))
    food = sum(1 for item in ru.listings if item["type"] == "eat")
    return sights < THIN_SIGHTS or food < THIN_FOOD


def fetch_articles(place: dict, llm: dict | None) -> tuple[Article | None, Article | None]:
    ru = fetch_article("ru", RU_TITLE_OVERRIDES.get(place["id"], place["wiki_ru"]))
    if llm is None or not needs_fallback(ru):
        return ru, None
    en_title = ru.langlinks.get("en") if ru else EN_TITLES_WITHOUT_RU.get(place["id"])
    return ru, fetch_article("en", en_title) if en_title else None


def fetch_p18(qids: Iterable[str]) -> dict[str, str]:
    found = {}
    for chunk in batches(sorted({q for q in qids if q}), 50):
        data = get_json(
            WIKIDATA_API,
            {"action": "wbgetentities", "ids": "|".join(chunk), "props": "claims", "format": "json"},
        )
        for qid, entity in data.get("entities", {}).items():
            claims = entity.get("claims", {}).get("P18", [])
            value = claims[0].get("mainsnak", {}).get("datavalue", {}).get("value") if claims else None
            if isinstance(value, str):
                found[qid] = value
    return found


def file_title(name: str | None) -> str | None:
    cleaned = FILE_PREFIX.sub("", (name or "").strip()).replace("_", " ").strip()
    return f"File:{cleaned[:1].upper()}{cleaned[1:]}" if cleaned else None


def usable_photo(page: dict | None) -> dict | None:
    info = ((page or {}).get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata", {})
    licence = meta.get("LicenseShortName", {}).get("value", "")
    author = strip_html(meta.get("Artist", {}).get("value", ""))
    if info.get("mediatype") != "BITMAP" or not info.get("thumburl") or not author:
        return None
    url = THUMB_HOST.sub(UPLOAD_HOST, info["thumburl"].split("?")[0])
    file_url = info.get("descriptionurl", "")
    if (
        not FREE_LICENCE.match(licence)
        or not url.startswith(UPLOAD_HOST)
        or not file_url.startswith(FILE_PAGE)
    ):
        return None
    return {
        "url": url,
        "width": info["thumbwidth"],
        "height": info["thumbheight"],
        "author": author,
        "license": licence,
        "file_url": file_url,
    }


def fetch_commons(titles: Iterable[str], width: int) -> dict[str, dict]:
    found = {}
    for chunk in batches(sorted(set(titles)), COMMONS_BATCH):
        data = get_json(
            COMMONS_API,
            {
                "action": "query",
                "titles": "|".join(chunk),
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mediatype",
                "iiurlwidth": width,
                "format": "json",
                "formatversion": "2",
            },
        )
        query = data.get("query", {})
        alias = {
            **{n["from"]: n["to"] for n in query.get("normalized", [])},
            **{r["from"]: r["to"] for r in query.get("redirects", [])},
        }
        by_title = {page["title"]: page for page in query.get("pages", []) if "title" in page}
        for title in chunk:
            photo = usable_photo(by_title.get(alias.get(title, title)))
            if photo:
                found[title] = photo
    return found


def resolve_photos(articles: dict[str, tuple[Article | None, Article | None]]) -> Photos:
    pages = [page for pair in articles.values() for page in pair if page]
    listings = [item for page in pages for item in page.listings]
    p18 = fetch_p18(
        [page.qid for page in pages if page.qid] + [item["wikidata"] for item in listings if item["wikidata"]]
    )
    place_titles = [file_title(n) for page in pages for n in page.images] + [
        file_title(p18[page.qid]) for page in pages if page.qid in p18
    ]
    listing_titles = [file_title(item["image"]) for item in listings] + [
        file_title(p18[item["wikidata"]]) for item in listings if item["wikidata"] in p18
    ]
    return Photos(
        place=fetch_commons([t for t in place_titles if t], PLACE_PHOTO_WIDTH),
        listing=fetch_commons([t for t in listing_titles if t], LISTING_PHOTO_WIDTH),
        p18=p18,
    )


def pick_photo(candidates: list[str], index: dict[str, dict]) -> dict | None:
    usable = [index[c] for c in candidates if c in index]
    landscape = [p for p in usable if p["width"] >= 1.2 * p["height"]]
    ranked = landscape or usable
    return ranked[0] if ranked else None


def p18_title(photos: Photos, qid: str | None) -> str | None:
    return file_title(photos.p18.get(qid)) if qid else None


# Text rules


def tidy_dashes(text: str) -> str:
    """Replaces em and en dashes with plain punctuation, but keeps dashes inside «» and quotes."""
    pieces = QUOTED.split(text)
    return "".join(
        piece if i % 2 else re.sub(r"\s*[–—]\s*", ", ", re.sub(r"(?<=\d)\s*[–—]\s*(?=\d)", "-", piece))
        for i, piece in enumerate(pieces)
    )


def word_cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit - 1].rsplit(" ", 1)[0]
    return f"{head.rstrip(',;:')}…" if head else ""


def cut_text(text: str, limit: int, max_sentences: int | None = None) -> str:
    sentences = SENTENCE_END.split(tidy_dashes(text).strip())
    chosen: list[str] = []
    for sentence in sentences[:max_sentences]:
        if len(" ".join([*chosen, sentence])) > limit:
            break
        chosen.append(sentence)
    return " ".join(chosen) if chosen else word_cut(sentences[0], limit)


def is_ota(url: str) -> bool:
    return any(host in url.lower() for host in OTA_HOSTS)


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def checked_coords(listing: dict, geo: tuple[float, float] | None) -> tuple[float | None, float | None]:
    lat, lon = listing["lat"], listing["lon"]
    if lat is None or lon is None or geo is None:
        return None, None
    limit = VICINITY_KM if listing["type"] == "vicinity" else LISTING_KM
    return (lat, lon) if distance_km((lat, lon), geo) <= limit else (None, None)


# LLM (OpenAI-compatible); the key is read from .env and never printed


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            pairs[key.strip()] = value.strip().strip("\"'")
    return pairs


def load_llm() -> dict | None:
    env = read_env(ENV_PATH)
    config = {
        "api_key": env.get("LLM_API_KEY", ""),
        "base_url": env.get("LLM_BASE_URL", "").rstrip("/"),
        "model": env.get("LLM_MODEL", ""),
    }
    if not all(config.values()):
        print("LLM not configured: English listings are dropped and dishes are left empty.")
        return None
    return config


def chat(llm: dict, body: dict) -> str:
    for attempt in range(3):
        response = httpx.post(
            f"{llm['base_url']}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {llm['api_key']}"},
            timeout=120,
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        if response.status_code not in (429, 500, 502, 503):
            raise RuntimeError(f"LLM request failed with HTTP {response.status_code}")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("LLM request kept failing")


def llm_text(llm: dict, system: str, user: str) -> str:
    body = {
        "model": llm["model"],
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    return cached_json(["llm", body], lambda: {"text": chat(llm, body)})["text"]


def translate(text: str, llm: dict) -> str:
    return cut_text(llm_text(llm, TRANSLATE_PROMPT, text), SUMMARY_MAX, 2)


def parse_dishes(raw: str) -> list[dict]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        print("  dishes: LLM answer was not JSON, skipped")
        return []
    dishes = data.get("dishes", []) if isinstance(data, dict) else []
    return [d for d in dishes if isinstance(d, dict)]


def grounded(name: str, passage: str) -> bool:
    stem = name.lower()[:-2] if len(name) > 5 else name.lower()
    return stem in passage.lower()


def extract_dishes(passage: str, llm: dict | None) -> list[dict]:
    if llm is None:
        return []
    dishes, seen = [], set()
    for item in parse_dishes(llm_text(llm, DISH_PROMPT, passage)):
        name = str(item.get("name", "")).strip()
        if not name or name.lower() in seen or not grounded(name, passage):
            continue
        seen.add(name.lower())
        dishes.append({"name": name, "note": tidy_dashes(str(item.get("note", "")).strip())})
    return dishes


# Per place


def candidate_listings(ru: Article | None, en: Article | None, llm: dict | None) -> list[dict]:
    pool = [*(ru.listings if ru else ()), *(en.listings if en and llm else ())]
    seen, kept = set(), []
    for item in pool:
        group = "food" if item["type"] in FOOD_TYPES else "sight"
        key = (group, item["name"].lower())
        if not item["description"] or is_ota(item["url"]) or key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def enrich(listing: dict, geo: tuple[float, float] | None, photos: Photos) -> dict:
    lat, lon = checked_coords(listing, geo)
    candidates = [c for c in (file_title(listing["image"]), p18_title(photos, listing["wikidata"])) if c]
    return {**listing, "lat": lat, "lon": lon, "photo": pick_photo(candidates, photos.listing)}


def rank(listings: list[dict]) -> list[dict]:
    return sorted(
        listings,
        key=lambda item: (
            not item["star"],
            -((item["lat"] is not None) + (item["photo"] is not None)),
            item["lang"] == "en",
        ),
    )


def finalize(listing: dict, llm: dict | None) -> dict | None:
    if listing["lang"] == "en":
        summary = translate(listing["description"], llm)
    else:
        summary = cut_text(listing["description"], SUMMARY_MAX, 2)
    if not summary:
        return None
    return {
        "type": listing["type"],
        "name": listing["name"],
        "alt": listing["alt"],
        "lat": listing["lat"],
        "lon": listing["lon"],
        "wikidata": listing["wikidata"],
        "star": listing["star"],
        "hours": listing["hours"],
        "price": listing["price"],
        "address": listing["address"],
        "summary": summary,
        "photo": listing["photo"],
        "lang": listing["lang"],
        "source_url": listing["source_url"],
    }


def number(place_id: str, listings: list[dict]) -> list[dict]:
    counts: Counter = Counter()
    numbered = []
    for listing in listings:
        counts[listing["type"]] += 1
        numbered.append({"id": f"{place_id}-{listing['type']}-{counts[listing['type']]:02d}", **listing})
    return numbered


def place_photo(articles: tuple[Article | None, Article | None], photos: Photos) -> dict | None:
    names = [file_title(n) for page in articles if page for n in page.images]
    qid = next((page.qid for page in articles if page and page.qid), None)
    candidates = [c for c in [*names, p18_title(photos, qid)] if c]
    return pick_photo(candidates, photos.place)


def build_place(
    place: dict,
    articles: tuple[Article | None, Article | None],
    photos: Photos,
    llm: dict | None,
) -> dict:
    ru, en = articles
    geo = next((page.geo for page in articles if page and page.geo), None)
    enriched = [enrich(item, geo, photos) for item in candidate_listings(ru, en, llm)]
    sights = rank([item for item in enriched if item["type"] in SIGHT_TYPES])[:MAX_SIGHTS]
    food = rank([item for item in enriched if item["type"] in FOOD_TYPES])[:MAX_FOOD]
    finished = [out for out in (finalize(item, llm) for item in (*sights, *food)) if out]
    passage = ru.food_intro if ru else None
    lat, lon = geo or (None, None)
    return {
        "title": place["name"],
        "source_url": f"https://ru.wikivoyage.org/wiki/{place['wiki_ru'].replace(' ', '_')}",
        "lat": lat,
        "lon": lon,
        "photo": place_photo(articles, photos),
        "food_intro": cut_text(passage, FOOD_INTRO_MAX) if passage else None,
        "dishes": extract_dishes(passage, llm) if passage else [],
        "listings": number(place["id"], finished),
    }


def summary_line(place_id: str, entry: dict, articles: tuple[Article | None, Article | None]) -> str:
    listings = entry["listings"]
    sights = sum(1 for item in listings if item["type"] in SIGHT_TYPES)
    translated = sum(1 for item in listings if item["lang"] == "en")
    return (
        f"{place_id:16} sights={sights:2} food={len(listings) - sights} dishes={len(entry['dishes'])} "
        f"photo={'yes' if entry['photo'] else 'no'} translated={translated} "
        f"ru={'ok' if articles[0] else 'missing'} en={'ok' if articles[1] else '-'}"
    )


def main() -> None:
    places = json.loads(PLACES_PATH.read_text(encoding="utf-8"))["places"]
    llm = load_llm()
    articles = {place["id"]: fetch_articles(place, llm) for place in places}
    print(f"Fetched {len(places)} places, resolving photos...", flush=True)
    photos = resolve_photos(articles)
    guide = {}
    for place in places:
        entry = build_place(place, articles[place["id"]], photos, llm)
        guide[place["id"]] = entry
        print(summary_line(place["id"], entry, articles[place["id"]]), flush=True)
    payload = {
        "about": ABOUT,
        "fetched_at": datetime.now(UTC).date().isoformat(),
        "places": guide,
    }
    SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(guide)} places to {SEED_PATH}")


if __name__ == "__main__":
    main()
