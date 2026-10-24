# 08: How the data connects, and how we keep it honest

[07](./07-data-sources.md) covers where each fact comes from. This page covers how the facts **join**, so the agent can answer a vague request with a chain of facts it can cite and the user can correct.

## The chain, on the golden query

«хочу к тёплому морю в ноябре, недорого, с ребёнком, без долгих перелётов», assuming departure from Moscow. All numbers are illustrative; real ones come from the tables below.

| Step | Join | Result |
|---|---|---|
| 1. Where is the sea warm in November? | `place` × `place_month` (month 11, `sea_temp ≥ 24`) | Hurghada, Sharm el-Sheikh, Dubai, Phuket, Nha Trang. Sochi drops out (sea about 15 °C) |
| 2. Which of them is a short flight? | `route` from MOW, `block_min ≤ 360` | Phuket and Nha Trang drop out (9 to 10 h) |
| 3. Can a Russian passport go? | `visa_rule` by country, with `checked_on` | Rule and "checked on" date for each place |
| 4. Is the date a holiday? | `calendar_day` | 4 Nov is a day off, so the long weekend raises prices that week |
| 5. What does it cost for 2 adults + 1 child? | `fare` for the dates + `night` for hotels that take children | Total for 7 nights, cheapest first |
| 6. Do the times fit? | arrival (local time + zone) + `transfer.minutes` vs hotel check-in | «Прилёт 10:05, трансфер 25 мин, заселение с 14:00: 3,5 часа ожидания» |

**Every number in the answer points to a row:** id, source, date and whether it's real, estimated or synthetic. That's how the agent explains "why", and how the user can say "no, from Kazan" and only steps 2, 5 and 6 rerun.

## Entities and keys

| Entity | Key | Main fields | Joins to | Comes from |
|---|---|---|---|---|
| `place` | Wikidata QID | `name_ru`, `name_en`, `country` (ISO 2), `lat`, `lon`, `tz`, `kind` (city, resort, region), `tags` (sea, mountains, nature, food) | everything | Wikidata, GeoNames |
| `place_month` | QID + month | `air_max`, `air_min`, `rain_days`, `sun_hours`, `sea_temp` (coastal only), `wind_p90`, `years` | `place` | Open-Meteo, Copernicus |
| `airport` | IATA | `name`, `lat`, `lon`, `tz`, `place_qid` | `place`, `route` | OurAirports, GeoNames |
| `route` | origin + destination + mode | `distance_km`, `block_min`, `block_kind` (scheduled or estimated), `direct`, `carriers`, `checked_on` | `airport`, `fare` | curated table + formula |
| `fare` | route + date | `price_rub`, `kind` (cached or synthetic), `fetched_at`, `expires_at` | `route` | Travelpayouts or synthetic |
| `hotel` | our id (OSM id kept if real) | `place_qid`, `lat`, `lon`, `stars`, `rooms`, `beach_m`, `check_in`, `check_out`, `kids`, `pets`, `step_free` | `place`, `rate_plan`, `transfer` | OSM or generator |
| `rate_plan` | hotel + room group + meal + payment | `meal` (room only, breakfast, half board, all inclusive), `free_cancel_days`, `penalty_pct`, `pay` (now or at hotel) | `hotel`, `night` | Ostrovok API shape, synthetic |
| `night` | rate plan + date | `price_rub`, `rooms_left` | `rate_plan` | computed on request, never stored |
| `transfer` | airport or station + hotel | `minutes`, `km`, `price_rub` (estimated) | `airport`, `hotel` | OSRM, per-km estimate |
| `calendar_day` | country + date | `day_type` (work, off, short), `holiday`, `long_weekend_id` | `fare`, `night` by date | official calendar |
| `visa_rule` | country | `rule`, `days`, `checked_on`, `source_url`, `confidence` | `place` by country | official pages |
| `fx_rate` | currency + date | `rate_rub` | any foreign price | CBR |
| `chunk` | QID + section + language | `text`, `embedding`, `source_url`, `licence` | `place` | Wikivoyage, our curated lines |

**Provenance on every row.** Fact tables also carry:
- `source` and `source_url`;
- `fetched_at` and `licence`;
- `kind` (real, estimated, synthetic);
- `valid_from` and `valid_to` where the fact can expire.

The UI uses `kind` to label «оценка» or «смоделировано». The agent cites `source_url` when it explains a pick.

## Sources disagree, and we keep every answer (built)

Two sources rarely agree to the decimal. Copernicus and Open-Meteo give different sea temperatures. One site says 30 visa-free days, another says 60. If one value overwrites the other, nobody knows there was a disagreement. So every source keeps its own value, and we choose at read time.

- **What a fact is.** Every fact has:
  - the thing it's about: `place` + QID, `hotel` + our id, or `country` + ISO code;
  - an `attribute`;
  - an optional `period`: `m11` for a month normal, `2026-11-14` for one date;
  - a `value` and a `unit`;
  - provenance: `source`, `source_url`, `source_tier`, `kind`, `fetched_at`, `valid_until`.

  All facts live in one `facts` table. The entity tables above are the logical view of it.
- **Each source keeps one current value per fact.** A re-fetch from the same source replaces only that source's value.
- **Checked on the way in.**
  - Known attributes declare a canonical unit, a valid range and a tolerance, e.g. `sea_temp`: °C, −2 to 35, ±1.
  - Other units are converted as they arrive: °F → °C, hours → minutes, inches → mm.
  - An unknown unit or an out-of-range value is rejected.
  - An attribute nobody registered yet (say `food_options`) is stored as given, so new kinds of data need no schema change.
  - Every value must be valid JSON up to 2000 characters (no NaN), links must be http(s), and times are stored in UTC.
- **Only adapters and a checking script write facts.** The web-search agent writes to the KB in [09](./09-living-knowledge-base.md), and a fact moves from there into `facts` only after a person or a validation script checks it. So the agent can't label its own claim `official` or `real`.
- **How a value is picked:**
  - fresh beats expired;
  - real beats estimated beats synthetic;
  - official beats media beats community;
  - then the newest wins.

  If nothing is fresh, the newest expired value comes back marked `stale`, so the agent says «данные на …» instead of inventing a fresh one.
- **A disagreement is a result, not an error.** We get back:
  - the chosen value;
  - every other source's value;
  - a `conflict` flag when any of them differs beyond the tolerance.

  The agent then says the sources disagree and shows both.
- **One adapter per source.** An adapter turns that source's own shape into facts, and reads units from the response instead of assuming them. The first one turns Open-Meteo daily data into monthly normals. A new source is a new adapter; nothing else changes.

The code is in `backend/app/facts/` (model, resolve, repository, service, adapters), with tests in `backend/tests/test_facts.py`, `test_facts_store.py` and `test_open_meteo_adapter.py`. A live run on 10 years of Hurghada data gives a November average high of 26.3 °C, low of 19.6 °C and 0.1 rainy days.

## Adaptive, not a fixed catalogue (planned)

1. **Build steps become functions the agent can call live.** For a place we don't have yet, the agent:
   - looks it up in Wikidata;
   - runs the climate adapter;
   - estimates routes from coordinates;
   - saves the result to the Docker volume.

   The same code runs before the demo and during it.
2. **Typed fields only where the code calculates.** Price, coordinates, times and durations are typed and validated. Everything else (features, policies, mood) is an open attribute or a knowledge base entry ([09](./09-living-knowledge-base.md)).
3. **Prices are calculated on request.** The synthetic calendar is a seeded formula, so price(hotel, date, rate) is computed when it's asked for. Any date works and nothing piles up. Only mock bookings are stored.
4. **Routes are estimated for any airport pair** from coordinates. The curated table only corrects the estimate, and live data overrides both.
5. **Embeddings record their model** (`embedding_model`, `embedded_at`). The model can change, and old vectors get re-embedded gradually.
6. **Storage stays behind the repository layer.**
   - SQLite in WAL mode for the demo.
   - Postgres with pgvector on the same schema once we pass about a million vectors or many writers at once.
7. **The most-used facts are re-checked first.** The background job counts how often each fact is read and refreshes the popular ones before they expire. User corrections flag facts as wrong.

## Quality rules

1. **Join by id, never by name.**
   - Places join on the QID, airports on IATA, hotels on our own id.
   - Names, both Cyrillic and Latin spellings, are only used at build time, through one hand-checked mapping table.
2. **Completeness gate.** A place enters the catalogue only when it has all of these:
   - 12 `place_month` rows, plus `sea_temp` if it's a beach place;
   - at least one route from Moscow with a duration;
   - a visa rule if it's abroad;
   - at least a handful of hotels.

   Forty complete places beat four thousand half-filled ones.
3. **Validate on the way in.**
   - Ranges: air −50 to 50 °C, sea −2 to 35 °C, block time 0.5 to 20 h, price above zero.
   - One unit per field.
   - A sea temperature point must be over water.
   - Every time has a time zone.
4. **Time is local wall-clock time plus an IANA zone.**
   - Compare in UTC.
   - Overnight trains and flights across zones are computed from ISO timestamps, never from a date plus a clock time.
   - Replanning "+2 days" re-queries the timetable, because trains run on certain weekdays only.
5. **Freshness per kind of fact.**
   - Fares carry `expires_at`.
   - Visa rules show `checked_on` and are rechecked on 28 Oct, before the submission.
   - Climate normals don't change.
   - Rates are daily.
6. **One curve drives price and availability.** In the synthetic calendar, the same occupancy number sets the price and the rooms left. The demo can never show a sold-out hotel at a bargain price.
7. **Reproducible.** Synthetic data comes from a fixed seed, so a juror sees the same results we tested against.
8. **Data tests in pytest, run on the committed seed:**
   - every place passes the completeness gate;
   - every hotel has a place and at least one rate plan;
   - every route has a duration;
   - no `rooms_left` below zero;
   - no fact without a source.

## Synthetic hotel calendar

There is no open source of real hotel prices and availability for our destinations, so we model them. The model is calibrated on real figures and declared as synthetic.

```
price(h, d, r) = base(stars, region)
               × hotel_factor(h)          seeded lognormal, σ ≈ 0.2
               × season(place, month)     monthly index, mean 1.0
               × weekday(d) × lead(d − today)
               × holiday(d)               long weekend bump from calendar_day
               × meal(r) × flex(r)        refundable costs more than non-refundable
               × noise(seed(h, d, r))

rooms_left(h, d) = rooms(h) × (1 − occupancy(place, month, weekday)) + seeded noise, never below 0
when occupancy is high, price rises 10 to 30% and some rate plans close
```

| Input | Calibrated on |
|---|---|
| `base` | RUTI class averages for Russia (8,204 ₽ / 9,158 ₽ / 14,582 ₽ by class); Dubai and Bangkok ADR abroad; Rosstat by region once downloaded |
| `season`, `occupancy` | Monthly occupancy from Rosstat, Türkiye, Dubai and Thailand figures |
| `weekday`, `lead` | Shapes from Hotel Booking Demand and the Inside Airbnb calendars |
| `flex` and the share of refundable rates | Cancellation rate in Hotel Booking Demand |
| `meal` | Our declared multipliers per meal plan |

We commit only these parameters, with a `calibration.json` that names the source of each, never other datasets' rows. The calendar itself is never stored: each price is computed when it's asked for, from the hotel, the date, the rate plan and the seed. Rate plans mirror Ostrovok's own model: hotel → room group → rate with meal, payment type and cancellation penalties ([07](./07-data-sources.md#etg--ostrovok-api-v3-copy-the-shape-not-the-data)).

## What we embed and what we filter

- **Filter exactly, in SQL:**
  - month, sea and air temperature;
  - flight time, budget, visa, dates;
  - children, pets, accessibility, cancellation terms.

  These must be right every time, so they never go through vector search.
- **Embed the soft meaning:**
  - Wikivoyage sections (Understand, See, Do);
  - one or two curated "vibe" lines per place;
  - hotel descriptions.

  That's what answers «тишина и природа», «вкусно кормят и можно гулять пешком» or «как в Европе, только без визы».
- **Order:**
  1. Parse the request.
  2. Hard filters give the candidates.
  3. Vector search ranks the candidates by the soft part.
  4. The LLM explains, citing fact rows.

  Every chunk carries its place QID, so a vector hit joins straight back to its facts.
- **Languages:** embed both the Russian and English text; the requests are Russian.
- The embedding model and index setup are decided separately and are not covered here.
- The agent also grows its own knowledge base from web search; its entry shape and rules are in [09](./09-living-knowledge-base.md).
- Chunks from Wikivoyage stay CC BY-SA, so the index file keeps that licence notice.

## Build pipeline (proposal)

```
data/
  build/          scripts we run before the demo, never inside the container
    places.py       Wikidata + GeoNames → place
    climate.py      Open-Meteo + Copernicus → place_month
    airports.py     OurAirports + curated routes → airport, route
    hotels.py       OSM extract or generator → hotel, rate_plan
    transfers.py    OSRM matrix → transfer
    texts.py        Wikivoyage dumps → chunk (+ embeddings)
    calendar.py     curated official calendar → calendar_day
  curated/        hand-made tables, a source on every row: routes, visa rules, calendar, vibe lines
  seed.sqlite     the committed result, loaded by the app at start
  ATTRIBUTION.md  every source, its licence and its credit line
```

- **Build once, commit the seed.** The container needs the internet only for the LLM and the optional live APIs.
- **Live adapters** (Travelpayouts, Yandex Schedules, CBR) call out with a timeout and fall back to the seed. Their keys live in `.env`.

## Licence map

| Source | Licence | What we must do | Commit? |
|---|---|---|---|
| Wikidata | CC0 | Nothing (credit is appreciated) | Yes |
| OurAirports | Public domain | Nothing | Yes |
| GeoNames | CC BY | Credit with a link | Yes |
| Open-Meteo | CC BY 4.0, free tier non-commercial | Credit; commercial use needs their paid plan | Monthly aggregates |
| Copernicus Marine | To check | Attribution line | After the check |
| Wikivoyage | CC BY-SA 4.0 | Credit, share-alike, separate file | Yes, staying CC BY-SA |
| OpenStreetMap | ODbL 1.0 | «© OpenStreetMap contributors»; a derived database stays ODbL | Separate file, after the experts answer |
| Yandex Schedules | Yandex API terms | Attribution in the UI; no storing | No |
| Travelpayouts | Terms not read yet | Read them first | Not yet |
| Hotel Booking Demand, Inside Airbnb | CC BY 4.0 (to confirm) | Credit | Derived parameters only |
| CBR | None stated | Cite the source | A dated fallback rate |
| Commons images | Per file | Credit per file | Yes, with a credits table |

**Rules 7.3 and 7.4** pass the rights in our submission to Ostrovok. Share-alike data (CC BY-SA, ODbL) can't become exclusively theirs. Keep it in separate files under its own licence, and ask the experts (question 9 in [05](./05-plan-and-checklists.md)).
