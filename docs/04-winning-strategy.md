# 04: How we win

## Thesis

**Chat is the input, the trip board is the product.** The agent doesn't answer in paragraphs. It *edits a live trip plan* on screen: constraints, destination cards, a comparison, a timeline with connection checks, and a cart. The user can talk to it or edit the board directly, and both paths trigger an incremental replan.

That one idea covers the brief's main demand («агент, который действует») and makes tasks 4 and 6 visible without any extra explanation.

## Eight differentiators, mapped to the brief

| # | Differentiator | Covers task | Why the jury cares |
|---|---|---|---|
| A | **Trip board UI**: chat on the left, live plan on the right (stacked on mobile) | 2, 3, 5 | Shows action instead of retelling |
| B | **Assume, show, ask at most once.** Fill gaps with sensible defaults shown as editable chips («Вылет: Москва ✎», «Ребёнок: от 2 до 11 лет ✎»). Ask only what blocks the next step, and still show options in the same turn | 1 | Hits «не анкета» precisely, and time to first recommendation stays low |
| C | **Why / what we gave up / risk** on every card, plus a list of **excluded options and why** («Таиланд: около 10 часов в пути, а вы просили без долгих перелётов») | 2, 4 | Transparent logic the user can correct |
| D | **Deterministic connection checker.** Code checks landing + transfer time against check-in, checkout against departure, night arrivals, child, pet and visa rules. It shows green, yellow or red with a suggested fix | 5 | Correctness the LLM can't fake. Engineers love it |
| E | **Replan as a diff.** The plan is structured state, and a change re-runs only the affected tools. Shows "what changed" and the price delta | 6 | Proves "not from scratch" |
| F | **Hotel fit** comes from the user's profile (kids, pet, quiet, beach type), including honest mismatches | 3, hotel story | The user story most teams will skip |
| G | **Eval harness**: about 40 test queries and a `make eval` that prints the brief's metrics table | extra 3, robustness | Numbers in the README and on a pitch slide |
| H | **Data provenance badges**: «живые данные» / «снимок от 24.10» / «демо-данные» | honesty rule | Turns the mock-data weakness into a trust signal |

## Scope (MoSCoW)

**Must (core score, nothing ships without these):**
- The full journey for any reasonable query: understand → destinations → options → compare → assemble → checkout (fake) → confirmation.
- The board (A), assumptions as chips (B), why/gave-up/risk (C), the connection checker (D), replan with a diff (E).
- Grounding: the LLM only quotes tool results.
- Docker, README, `/health`, video, and the `submission` tag.

**Should (cheap, visible wins):**
- Hotel fit and exclusions (F), the eval harness plus a metrics table (G), provenance badges (H).
- A responsive layout, which counts as the "mobile version" extra at almost no cost.
- Post-purchase basics: "can I check in early?" and "add a transfer to my booking", reusing the same tools on the confirmed booking.
- Memory: a profile saved per user (SQLite) and reused next session («в прошлый раз вы ездили с ребёнком 5 лет. Снова так?»).

**Could (only if Must and Should are solid by 28 Oct midday):**
- A Telegram bot over the same agent API.
- Multi-city trips.
- Voice input.

**Won't:**
- Real payment, real booking, user accounts or auth beyond a test user.
- Scraping Ostrovok, Booking or other OTAs (rules 6.5 and 6.6).
- Our own model training or fine-tuning.

## Architecture: as small as possible, robust on the jury's laptop

```
┌──────────────── browser (localhost:8080) ────────────────┐
│  Chat  │  Trip board: chips · cards · compare · timeline · cart │
└────────────┬───────────────────────────────────────────────┘
             │ HTTP + SSE (streamed progress: «ищу перелёты…»)
┌────────────▼──────────── app container (:8080) ───────────┐
│  API + static UI                                           │
│  Agent loop: LLM (OpenAI-compatible) ⇄ tools                │
│  TripState (typed JSON): constraints, assumptions,          │
│     candidates, selection, cart, booking                    │
│  Tools: destinations · climate · flights · trains · hotels  │
│         · transfers · compare · validate_itinerary · cart   │
│         · checkout(mock) · post_purchase                    │
│  Validator (pure code): timeline + rules checks             │
│  Data: seed snapshot (JSON/SQLite, committed) + live APIs   │
│        where keyless, always with a snapshot fallback       │
└────────────────────────────────────────────────────────────┘
```

Principles:
1. **The LLM decides, the code computes.** Prices, times, distances and connection checks never come from the model.
2. **It works offline except for the LLM.** The seed data is committed, so a juror gets the same results we tested against.
3. **One app container plus SQLite.** Fewer services means fewer failure points on someone else's laptop. Add Postgres only if a real need shows up.
4. **A plain tool-calling loop.** It's about 150 lines, easy to debug and stream. Reach for an agent framework only if the team already knows one well.
5. **The model is configured by env:** `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, plus an optional fallback model.

Stack is open, decide as a team: Python (FastAPI) fits Ostrovok's stack and juniors best. Frontend can be any SPA that builds into static files served by the same container.

## Data sources

The full research, with licences and links, is in [07-data-sources.md](./07-data-sources.md). How the facts join and how we check them is in [08-data-model.md](./08-data-model.md). The short version:

- **Places:** Wikidata is the master id. Wikivoyage text gets embedded. GeoNames gives time zones and OurAirports gives airports.
- **Weather:** Open-Meteo monthly normals. Sea temperature comes from Copernicus Marine, because Open-Meteo Marine only goes back to 2022.
- **Getting there:** Travelpayouts cached prices and Yandex Schedules timetables run at runtime only (Yandex forbids storing), with a committed fallback. Flight time is estimated from distance.
- **Hotels:** real places where the licence allows, with prices and availability synthetic but calibrated on real statistics, shaped like Ostrovok's own API.
- **Calendar, visas, rates:** the official production calendar, a hand-checked visa table with dates, and CBR rates.

**Don't use:** Amadeus Self-Service. It was shut down on 17 Jul 2026 and its keys no longer work ([PhocusWire](https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers)).

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The jury has no LLM key or provider when running locally | **High** | Fatal | **Ask organizers on 25 Oct** what key and provider they'll use. Support any OpenAI-compatible base URL. Put the key step at the top of the README. Add a deployed URL if allowed |
| The LLM provider is blocked from Russia (the jury is in Moscow) | Medium | Fatal | Pick a provider that works from Russia, or make one switchable through the env |
| The Docker build breaks on their machine | Medium | Fatal | CI runs `docker compose up` + curls `/health`. Pin versions, `platform: linux/amd64`, test a fresh clone on another teammate's laptop on 28 Oct |
| The live demo is slow or hangs | Medium | High | Streaming progress, a fast model for routing, timeouts, a recorded backup video ready to play |
| Hallucinated facts | High without guardrails | High | Tools-only facts, a validator, eval cases that check grounding |
| Scope creep and a half-finished journey | High | High | MoSCoW above. The core journey has to be end-to-end by 26 Oct evening |
| Late tag or late push | Low | Fatal | Tag rehearsal on 28 Oct, real tag by **08:00 MSK on 29 Oct** |
| Org invite still pending | **Now** | Blocks everything | Accept the GitHub org invite today |
