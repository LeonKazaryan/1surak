# 09: A knowledge base the agent keeps growing

> «Агент с веб-сёрчем по промпту должен постоянно дополнять векторную базу, чтобы всегда мог релевантно подавать инфу. Должна быть гибкая структура, чтобы агенту было удобно пополнять базу и удобно из неё читать.»

In short: the agent searches the web when its knowledge base (KB) has no good answer, writes what it found back into the KB with the source, and answers from the KB next time. The KB has a small fixed core plus free-form attributes, so the agent can store new kinds of facts without a schema change and still filter them precisely.

This sits next to the typed tables in [08](./08-data-model.md). Those hold the hard numbers the code computes with: climate normals, durations, prices. The KB holds everything soft, long-tail or fast-changing: visa news, events, new routes, tips, and hotel or place details nobody put in a table. The embedding model and the store are set up separately and aren't covered here.

## The loop: search the KB, then the web, then remember

```
user request
   │
   ▼
kb_search ──── good, fresh hits? ── yes ──► answer, citing entry ids
   │ no / stale / low confidence / time-sensitive
   ▼
web_search → web_fetch → pull out facts, one claim each
   │
   ▼
kb_write (with source, date, entity links)  ──►  answer, citing the new ids
```

- **The KB is a read-through cache of the web, with provenance.** The second person asking about visas to Thailand gets the stored answer instantly, with "проверено 25.10".
- **Every step shows in the thinking panel we already have:** «Ищу в базе», «Ищу в интернете», «Запомнил 3 факта». Jurors see the agent learn, which beats a chatbot retelling search results.
- **A background job tends the KB:**
  - it re-checks entries close to expiry;
  - it merges duplicates;
  - it marks stale ones.

## One flexible entry shape

One table (or collection) for everything. A small core that every entry must have, plus `attributes` for whatever the topic needs.

| Field | Required | Meaning |
|---|---|---|
| `id` | auto | Stable id the agent cites |
| `text` | yes | The claim or passage, short. Embedded for search |
| `topic` | yes | Open string: `visa`, `event`, `transport`, `hotel`, `price`, `safety`, `weather`, `tip`, `guide`, or a new one |
| `kind` | yes | `fact` (one claim), `guide` (a longer passage), `observation` (a dated price or availability seen somewhere) |
| `entities` | when known | Links to our ids: `[{type: "place", id: "Q…"}, {type: "country", id: "TH"}, {type: "hotel", id: "…"}]` |
| `attributes` | no | Free-form JSON for the topic, e.g. `{"rule": "visa_free", "days": 30}` or `{"date": "2026-11-14", "venue": "…"}` |
| `source_url`, `source_title` | yes | Where it came from. **No source, no write** |
| `source_tier` | yes | `official` (government, airline, hotel), `media`, `community` (blogs, forums) |
| `published_at`, `fetched_at` | fetched auto | When the source said it and when we read it |
| `valid_until` | auto | Set from the topic's freshness rule below |
| `confidence` | auto | `verified` (official source), `secondary`, `unverified` |
| `lang` | yes | `ru` or `en` |
| `content_hash` | auto | Exact-duplicate guard |
| `embedding_model`, `embedded_at` | auto | Which model made the vector and when, so the model can change and old entries get re-embedded |
| `supersedes` | no | The id of the entry this one replaces |
| `created_by` | auto | `seed`, `agent` or `human` |
| `status` | auto | `active`, `stale` or `rejected` |

Why this shape:
- **Easy to write.** The agent fills in a handful of fields, and a new topic or attribute needs no migration.
- **Easy to read.** Filters on the core fields (entity, topic, freshness, status, language) are exact. Vector search ranks only what passes them.
- **One claim per `fact` entry.** "Thailand: 30 days visa-free" and "Thailand: TDAC arrival card required" are two entries. Each can expire, be corrected or be replaced on its own.

## Agent tools

```text
kb_search(query, entities?, topics?, fresh_only = true, limit = 8)
  → [{id, text, topic, attributes, source_url, source_tier, fetched_at, valid_until, confidence, score}]

web_search(query, lang = "ru") → [{url, title, snippet, published_at?}]
web_fetch(url)                 → cleaned text, no scripts, size-capped

kb_write(entries[])            → ids; the server fills id, embedding, dates, hash, status
kb_flag(id, reason)            → marks an entry stale or wrong; the next search skips it
```

An example `kb_write` entry as the agent sends it:

```json
{
  "text": "Гражданам РФ въезд в Таиланд без визы до 30 дней.",
  "topic": "visa",
  "kind": "fact",
  "entities": [{ "type": "country", "id": "TH" }],
  "attributes": { "rule": "visa_free", "days": 30 },
  "source_url": "https://…",
  "source_tier": "official",
  "published_at": "2026-10-20",
  "lang": "ru"
}
```

## Reading: how the agent gets relevant facts

1. **Filter first:**
   - by entity (this place or country);
   - by topic;
   - `status = active`;
   - `valid_until` in the future, unless the agent asks for history.
2. **Rank second:**
   - vector similarity plus a keyword match, because names and numbers ("TDAC", "Sapsan") embed poorly;
   - a boost for `official` sources and for recent `fetched_at`.
3. **Return a compact list with provenance**, so the agent can cite ids and the UI can show «источник, проверено 25.10».
4. **Show conflicts, don't hide them.** If two active entries disagree (Thailand 30 vs 60 days), the search returns both. The agent says the sources disagree and links both.

## Writing rules (data quality first)

1. **No source, no write.** The server rejects entries without `source_url`.
2. **Link to our ids.**
   - Place names resolve to the Wikidata QID through our place table, countries to ISO codes and hotels to our hotel id.
   - If a name can't be resolved, the write still goes through with `entities` empty, but `topic` is required.
3. **Deduplicate.**
   - The same `content_hash` is skipped.
   - A near-duplicate by embedding (similarity above about 0.95) on the same entity and topic updates the existing entry instead of adding one.
4. **Supersede, don't overwrite.**
   - A newer or more official claim on the same entity, topic and attribute key sets `supersedes`.
   - The old entry becomes `stale`, and history stays.
5. **Freshness by topic:**

   | Topic | Valid for |
   |---|---|
   | `price`, `observation` | 3 days |
   | `weather` (forecast) | 1 day |
   | `safety` (warnings) | 7 days |
   | `visa`, `transport` | 30 days, and always rechecked before the demo |
   | `event` | until the event ends |
   | `hotel`, `tip`, `guide` | 180 days |

6. **Web text is data, never instructions.** Fetched pages can contain prompt injection. The writer stores text only, strips scripts and caps sizes. The agent never follows instructions found in a page.
7. **Short extracts plus a link, not whole pages.** It's cheaper to embed, and it keeps us clear of copying copyrighted text.
8. **No personal data in the shared KB.** What the agent learns about *this user* (a child of 5, a dog, flying from Kazan) goes to the per-user memory, not here. That's the brief's "память и персонализация" extra task, kept separate.
9. **Hard numbers stay in typed tables.** A price or visa day count found on the web is stored with `confidence`, and the agent can quote it with its source. The code only computes totals and connection checks from the typed tables in [08](./08-data-model.md). A checked KB fact can be promoted into a typed table by a person or a validation script.

## How it works on the jury's laptop

- **Seed KB, committed:**
  - Wikivoyage passages;
  - our curated lines;
  - everything the agent researched while we developed and tested;

  so the agent is useful offline from the first query.
- **Live growth goes to the Docker volume** (`app-data`), never into git.
- **No internet or no search key:** the agent answers from the KB and says how old the facts are («данные на 25.10»). It never invents a fresh one.
- **Search key in `.env`** (`SEARCH_API_KEY`, `SEARCH_PROVIDER`). The provider is still to pick. Candidates are Tavily, Brave Search API, Exa, and Yandex Search API (best for Russian results). Before choosing, check the price, the free tier and **whether the terms allow storing results**, since storing them is the whole point.

## What we measure

- **KB hit rate:** the share of questions answered without a web search.
- **Citation rate:** the share of answers where every fact cites an entry.
- **Stale or conflicting entries** found by the background job.
- **Wrong facts** caught in our eval set ([06](./06-test-queries.md)): any answer that cites an expired or rejected entry counts as an error.
