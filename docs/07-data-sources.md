# 07: Data sources, what to use and where to get it

Ostrovok gives us no data and no API, so everything below is ours to collect. Researched on **25 Oct 2026**. **Verified** means someone fetched the page that day. **Secondary** means a search snippet or a third-party site. **Unverified** means we could not confirm it, so check it by hand before relying on it.

How the facts connect, how we check their quality and what we embed is in [08-data-model.md](./08-data-model.md).

## The rule we pick sources by

More data is not better data. A fact earns its place only if it **joins** to a place and a date, so the agent can walk the chain **place → cost → availability → time**. One small, complete, connected source beats five loose ones. Every fact we store keeps its source URL, the date we fetched it, its licence and whether it is real, estimated or synthetic.

## The short answer

| Need                                 | Use                                                           | Real or synthetic             | How it ships                                                    | Licence                             |
| ------------------------------------ | ------------------------------------------------------------- | ----------------------------- | --------------------------------------------------------------- | ----------------------------------- |
| Place identity (the master id)       | **Wikidata** QIDs                                             | Real                          | Committed snapshot                                              | CC0                                 |
| Place text to embed                  | **Wikivoyage** ru + en dumps                                  | Real                          | Committed, cleaned sections                                     | CC BY-SA 4.0 (share-alike)          |
| Time zone, population, Russian names | **GeoNames** daily dump                                       | Real                          | Committed                                                       | CC BY 4.0                           |
| Airports and coordinates             | **OurAirports**                                               | Real                          | Committed                                                       | Public domain                       |
| Air climate by month                 | **Open-Meteo** Historical (ERA5), normals 1991 to 2020        | Real                          | Committed monthly aggregates                                    | CC BY 4.0, free tier non-commercial |
| Sea temperature by month             | **Copernicus Marine** reprocessed SST (licence to check)      | Real                          | Committed monthly aggregates                                    | Check first                         |
| Flight prices                        | **Travelpayouts / Aviasales Data API**                        | Real cached prices            | At runtime with a fallback; commit only once the terms allow it | Terms unverified                    |
| Flight duration                      | Great-circle estimate from OurAirports coordinates            | Estimated                     | Computed in code                                                | n/a                                 |
| Train and flight schedules           | **Yandex Schedules API v3**                                   | Real                          | **Runtime only**, the terms forbid storing                      | Attribution required                |
| Hotels                               | OSM hotel names and coordinates **or** fully synthetic hotels | Real places + synthetic rooms | See the ODbL warning below                                      | ODbL                                |
| Hotel prices and availability        | Synthetic calendar, **calibrated** on real statistics         | Synthetic, declared           | Committed                                                       | Our own                             |
| Hotel data shape                     | **ETG / Ostrovok API v3** schema, copied as a model only      | n/a                           | Our schema                                                      | Don't copy their data               |
| Transfer time                        | Self-hosted **OSRM** on a Geofabrik extract, precomputed      | Real durations                | Committed matrix                                                | ODbL                                |
| Holidays and long weekends           | Official production calendar (pravo.gov.ru), curated          | Real                          | Committed                                                       | Public legal text                   |
| Visa rules                           | Hand-checked table, one official page per country             | Real, dated                   | Committed with `checked_on`                                     | Our own                             |
| Ruble rates                          | **CBR** daily XML                                             | Real                          | Runtime plus a dated fallback                                   | No terms stated                     |
| Images                               | **Wikimedia Commons** with per-file credits, or none          | Real                          | Committed with a credits file                                   | Per file                            |

## 1. Places: identity, facts and text

### Wikidata: the master id for every place (use)
- **What:** QID, ru and en labels, country (P17), coordinates (P625), population (P1082), time zone (P421), IATA code (P238), image (P18), and sitelinks to Wikivoyage and Wikipedia.
- **Access:** SPARQL at `https://query.wikidata.org/sparql?format=json&query=...`, no key. There's no stated numeric limit, so back off on 429 and send a descriptive User-Agent. Bulk data comes from the dumps; the 2026-10-01 dump is complete. [Data access](https://www.wikidata.org/wiki/Wikidata:Data_access) (verified)
- **Licence:** CC0, safe to commit. [Licensing](https://www.wikidata.org/wiki/Wikidata:Licensing) (verified)
- **Pitfalls:**
  - A city's IATA code is often a metro code (Moscow Q649 returns `MOW`, verified by a live query). For flights, join on airport items instead (P31 airport).
  - "City" items include tiny villages, so filter by country and population.
  - Russian labels are sometimes missing; fall back to English.
  - Property numbers other than P238 were not checked live.

### Wikivoyage ru + en: the text we embed (use)
- **What:** guide articles per destination with Understand, Get in, See, Do, Eat, Sleep and Go next. Listings are templates with coordinates.
- **Access:** monthly dumps (`ruwikivoyage/20261001` and `enwikivoyage/20261001` are complete) or the MediaWiki API. [Dumps](https://dumps.wikimedia.org/backup-index.html) (verified)
- **Licence:** CC BY-SA 4.0. Credit the contributors, and anything derived from it stays CC BY-SA. Keep it in its own file with a licence notice. [Copyrights](https://en.wikivoyage.org/wiki/Wikivoyage:Copyrights) (verified on en; the ru page returned 404)
- **Pitfalls:**
  - "Get in" sections go stale: prices, visa rules and airlines change. Never take a fact from this text, only the mood and the "why go".
  - Russian coverage of resorts is thinner than English, so embed both languages.

### GeoNames: time zones, population, Russian names (use)
- **What:** geonameId, coordinates, IANA time zone, population, and alternate names including Russian.
- **Access:** use the daily `allCountries.zip`, not the API (a free account allows 10,000 credits a day). [Export](https://www.geonames.org/export/) (verified)
- **Licence:** CC BY, version not stated on the page. Show credit with a link.

### OpenStreetMap: hotels and beaches (use, with care)
- **What:**
  - Hotels: `tourism=hotel|guest_house|apartment|hostel` with `name`, `stars`, `rooms`, `addr:*`, `wheelchair`, `internet_access`, `check_in`, `breakfast`. [Tag:tourism=hotel](https://wiki.openstreetmap.org/wiki/Tag:tourism%3Dhotel) (verified)
  - Beaches: `natural=beach` with `surface` (sand, gravel, pebbles). [Tag:natural=beach](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dbeach) (verified)
- **Access:**
  - Extract once from Geofabrik: Russia is 3.9 GB, the South district 301 MB, with data up to 2026-10-23. [Geofabrik Russia](https://download.geofabrik.de/russia.html) (verified)
  - Don't call Overpass live in the demo. Its main instance asks for under 10,000 queries and 1 GB a day, and heavy use isn't supported. [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) (verified)
  - Don't use Nominatim at runtime: it allows 1 request a second and you must cache. Geocode once, offline. [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/) (verified)
- **Licence warning:** ODbL. A table of OSM hotels committed to a public repo is probably a *derivative database* (ODbL 4.4), so it must stay ODbL and be offered in machine-readable form. Two options:
  - (a) keep OSM rows in a separate file with an ODbL notice;
  - (b) generate hotels synthetically and use OSM only for the coordinates of beaches and centres.

  Ask the experts (see [05](./05-plan-and-checklists.md)). [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- **Pitfalls:**
  - Star ratings are often missing in Russia.
  - Many hotels are mapped as areas, so use the centroid.
  - The same hotel can appear as both a node and an area.
  - Pets and "family friendly" have no standard tags, so never promise them from OSM.

### Images (use Commons, or none)
- **Wikimedia Commons:** every file has its own licence (CC BY, CC BY-SA, PD). Record the author and licence per file in a credits table. [Reusing content](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia) (verified)
- **Avoid Unsplash for the jury build.** Its API terms require hotlinking the returned URLs, which breaks offline. [API terms](https://unsplash.com/api-terms) (verified)
- **Pexels:** free, no attribution required. A small committed set is probably fine; keep a credits file anyway. [Licence](https://www.pexels.com/license/) (verified)
- The rules forbid third-party images without rights (6.5), so no hotel photos from Ostrovok or Booking.

### Checked and not usable yet
- **OpenTripMap:** alive (a request without a key returns 401), but the quota and licence are unverified.
- **Russian register of classified accommodation:** it would give real hotel names, categories and room counts. The operator per secondary sources is Rosaccreditation, but the open-data format is unconfirmed and tourism.gov.ru didn't resolve. Open it by hand.
- **data.mos.ru hotel list:** the page didn't load. Open it by hand.

## 2. Climate and sea: the "warm sea in November" facts

### Open-Meteo Historical (ERA5): air climate normals (use)
- **What:** daily `temperature_2m_max`, `temperature_2m_min`, `precipitation_sum`, `precipitation_hours`, `sunshine_duration`, `wind_speed_10m_max`. ERA5 goes back to 1940 at 0.25°, ERA5-Land to 1950 at 0.1°. [Historical API](https://open-meteo.com/en/docs/historical-weather-api) (verified)
- **Request, one call per place:**
  `https://archive-api.open-meteo.com/v1/archive?latitude=43.58&longitude=39.72&start_date=1991-01-01&end_date=2020-12-31&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration,wind_speed_10m_max,precipitation_hours&timezone=auto`
  The `timezone` parameter is required when you ask for `daily`.
- **Aggregate per place and month:**
  - mean max and mean min temperature;
  - days with more than 1 mm of rain;
  - sunshine hours a day;
  - the 90th percentile of max wind.

  Store the years (1991 to 2020) and the source with every value.
- **Limits and licence:**
  - 10,000 calls a day, 5,000 an hour, 600 a minute.
  - The free tier is non-commercial; the data is CC BY 4.0. [Terms](https://open-meteo.com/en/terms) (verified)
  - Since the rights pass to Ostrovok, flag that commercial use needs their paid plan.
- **Pitfalls:**
  - ERA5 is a model reanalysis, not station data. Mountains (Altai, highland Dagestan) come out too cold.
  - Sunshine is modelled, so label it "оценка".

### Sea temperature (pick carefully)
- **Open-Meteo Marine** `sea_surface_temperature` is 0.08° but only goes back to **Jan 2022**. That's three or four Novembers, too few for a normal; use it only for "this year" values. Attribution goes to DWD and Open-Meteo, and the SST comes from Copernicus. [Marine API](https://open-meteo.com/en/docs/marine-weather-api) (verified)
- **Copernicus Marine** reprocessed L4 SST (`SST_GLO_SST_L4_REP_OBSERVATIONS_010_024`) has a long daily history and is the right source for monthly normals. It needs a free account and an attribution line; the licence for this product is unverified.
- **NOAA OISST:** daily at 0.25°, a well-known alternative. Licence unverified.
- **Pitfall:** a resort's grid cell is often land. Pick a sea point about 1 to 2 km offshore for sea temperature, and test the Red Sea, the Black Sea and the Caspian before trusting them.

## 3. Getting there: flights, trains, transfers

**Don't use** Amadeus Self-Service (shut down 17 Jul 2026), OpenFlights routes (last data June 2014), or the OSRM demo server in the product (1 request a second, non-commercial). [OpenFlights](https://openflights.org/data.html) (verified), [OSRM demo](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server) (verified)

### OurAirports: the airport table (use)
- **What:** `airports.csv` with `iata_code`, `icao_code`, `name`, `latitude_deg`, `longitude_deg`, `iso_country`, `municipality`, `scheduled_service`. Refreshed nightly; files dated 2026-10-24. **No time zone column**, so take it from GeoNames or Wikidata P421. [Data](https://ourairports.com/data/), [dictionary](https://ourairports.com/help/data-dictionary.html) (verified)
- **Licence:** public domain, safe to commit.

### Travelpayouts / Aviasales Data API: cached flight prices (maybe)
- **What:** the cheapest cached price per route and date: `price`, `airline`, `transfers`, `departure_at`, `return_at`, `expires_at` (v1), or `value`, `depart_date`, `found_at` (v2). Main endpoints carry **no duration**. [Docs](https://travelpayouts.github.io/slate/) (verified)
- **Request:** `GET https://api.travelpayouts.com/v2/prices/month-matrix?origin=MOW&destination=AER&currency=rub`, with the token in the `X-Access-Token` header. Server side only.
- **Limits:** per minute per endpoint, for example 300 a minute for the calendar (secondary). 429 when exceeded.
- **Pitfalls:**
  - A cached price is not a bookable price, and prices must not be used after `expires_at`.
  - The time zone of `departure_at` is not stated; check it against a sample.
  - Russian coverage depth is unverified.
- **Terms:** the terms page returned 403. Until someone reads it, call the API at runtime with a synthetic fallback and **commit no price rows**.

### Yandex Schedules API v3: real timetables (use at runtime)
- **What:** `/v3.0/search/` between stations or cities.
  - Departure and arrival as ISO times **with offset**, `duration` in seconds.
  - `thread` with carrier and number, `transport_type` (plane, train, suburban, bus), `has_transfers`.
  - Sometimes `tickets_info.places[].price`.

  [Search](https://yandex.ru/dev/rasp/doc/ru/reference/schedule-point-point) (verified)
- **Request:** `https://api.rasp.yandex-net.ru/v3.0/search/?apikey=KEY&from=c213&to=c2&date=2026-11-15&transport_types=train&format=json&lang=ru_RU&transfers=true`. Here `c…` is a city code and `s…` a station code.
- **Terms:**
  - Free key from the developer cabinet.
  - Only temporary caching is allowed; storing or changing the data is not.
  - Show «Данные предоставлены сервисом Яндекс Расписания» with a link. [Terms](https://yandex.ru/legal/rasp_api/), [attribution](https://yandex.ru/dev/rasp/doc/ru/reference/query-copyright) (verified)
  - The daily limit was not found; the "500 a day" figure is unverified.
- **So:** never put Yandex data in the committed seed. For offline, hand-curate a few key routes (Сапсан, Москва → Казань, overnight trains) from public timetables, labelled "ориентир, проверено <date>".
- **RZD** has no official API or GTFS, and scraping is risky. **Tutu.ru** has no public train API, only affiliate links.

### Which routes actually fly from Russia
There's no official list of permitted foreign routes. Media analyses of the winter schedule count about 43 countries, of which about 33 to 35 are realistic for tourists (secondary). Build our own route table by hand: origin city, destination airport, direct or not, carriers, and the date checked.

### Flight time when only the pair is known
Block time ≈ great-circle distance / 800 km/h + 0.5 h for taxi and climb. Compute the distance with haversine on OurAirports coordinates and mark the result `estimated`.

### Transfers: airport or station → hotel
- **Self-hosted OSRM** on the Geofabrik extract gives real car durations. Precompute a matrix of airport/station → each hotel and commit the minutes (ODbL attribution applies).
- **2GIS Routing API** covers car, taxi and public transport in Russian cities but is billed per point pair. Check prices and terms first. [Overview](https://docs.2gis.com/en/api/navigation/routing/overview) (verified)
- **Taxi price:** no documented Yandex Taxi price API was found. Use a declared per-km estimate by country.
- **Aeroexpress:** no API. Fares from news items are dated and mixed; label them "ориентир".
- **OpenRouteService:** the plans pages returned 404, so it's unverified.

## 4. Hotels: prices, availability, policies

**There is no open source of real hotel prices and availability for our destinations.** So the hotel layer is **synthetic but calibrated**, declared honestly in the UI and at the demo. We still use real hotels where we can (OSM names and coordinates).

### ETG / Ostrovok API v3: copy the shape, not the data
The public OpenAPI file shows how Ostrovok models a hotel offer. [openapi.json](https://api.ratehawk.com/openapi.json) (verified)
- Static hotel data: `GET /api/b2b/v3/hotel/static`, with reference lists for meals, beddings, taxes and amenities.
- A rate `b2b.Rate` has `meal`, `meal_data`, `payment_options`, `amenities_data` and `rg_ext` (room group).
- **Cancellation penalties hang off the payment type** (`b2b.PaymentType.cancellation_penalties`), not off the hotel.
- Rooms are grouped (`room_groups`).

Mirroring this makes our mock look like their world: hotel → room group → rate (meal, payment type, cancellation penalties with "free until" and a penalty after). The exact enum values weren't readable.

**Don't touch the ETG sandbox.** Third-party guides disagree on whether a test hotel books for real, and the terms page returned 404.

### Real numbers to calibrate the synthetic prices

| Anchor | Figure | Source |
|---|---|---|
| Russia, average summer 2026 hotel night | 11,285 ₽ (+3.5% y/y); 1 to 2★ 8,204 ₽, 3★ 9,158 ₽, 4 to 5★ 14,582 ₽ | RUTI via [finance.mail.ru](https://finance.mail.ru/article/v-rst-zayavili-o-podorozhanii-letnego-otdyiha-v-rossii-na-35-69210614/) (secondary) |
| Dubai, Jan to Aug 2026 | ADR AED 470, RevPAR AED 283 | [Emirates 24/7](https://www.emirates247.com/business/dubai-hotel-revenues-hit-dh6-billion-in-eight-months-as-697-million-visitors-arrive-in-2026/6251) (secondary) |
| Bangkok, H1 2026 | occupancy 76.2%, ADR THB 4,013 | [Knight Frank](https://content.knightfrank.com/research/2972/documents/en/bangkok-phuket-hotel-market-h1-2026-12985.pdf) (secondary) |
| Thailand outlook | national occupancy about 72 to 73% | [Krungsri](https://www.krungsri.com/en/research/industry/industry-outlook/services/hotels/io/2026-2028) (secondary) |
| Türkiye, licensed accommodation 2024 | occupancy 51.92% | [IKV note](https://www.ikv.org.tr/images/files/ikv_bilgi_notu_ab_konaklama_verileri_bared.pdf) (secondary) |
| Russia by region and month | Rosstat / EMISS hotel price and occupancy tables | [fedstat.ru](https://www.fedstat.ru) returned 403. **Open by hand**; this would be our best anchor |

For the **shape** of prices and bookings (not the level):
- **Hotel Booking Demand** (Antonio, Almeida, Nunes, Data in Brief 2019) has 119,390 bookings from two Portuguese hotels, 2015 to 2017. It includes `lead_time`, `is_canceled`, `adr`, `meal` and arrival dates, which gives weekday, lead-time and cancellation patterns. The licence is reported as CC BY 4.0; check it on the host before use.
- **Inside Airbnb** has per-date price and availability calendars for Istanbul (25 Sep 2026) and Bangkok (22 Sep 2026), under CC BY 4.0. It's apartments, not hotels, so use it only for weekend and season curves. [Get the data](https://insideairbnb.com/get-the-data/) (verified)
- We commit only the **derived parameters**, never their rows.

The formula and the consistency rule are in [08](./08-data-model.md#synthetic-hotel-calendar).

## 5. Calendar, visas, money, events

### Russian holidays and long weekends (use the official text)
- The 2026 and 2027 production calendars come from the government decree on pravo.gov.ru. Curate one small table of working days, days off and short days, and **compute** long weekends from it.
- Secondary sources already show 2027 (New Year 31 Dec 2026 to 10 Jan 2027; 1 to 3 and 8 to 10 May; 12 to 14 Jun; a 4 to 5 Nov block). Confirm against the decree before shipping. [Kontur](https://www.kontur-extern.ru/info/normativ/document/1/507840-proizvodstvennyy-kalendar-na-2027-god-dlya-shestidnevnoy-rabochey-nedeli-ot-30-04-2026) (secondary)
- **isdayoff.ru** gives a day type per date for RU, KZ, UZ and BY, but no licence is stated. Fine as a cross-check, not as the source. [isdayoff.ru](https://isdayoff.ru/) (verified)
- **Holidays at the destination:** Nager.Date by country and year (open source; licence and coverage to check). [nagerholidays.com](https://nagerholidays.com/) (verified). Ramadan and Chinese Golden Week also matter for Egypt, the UAE and China.

### Visa rules for a Russian passport (highest-risk data)
Store `(country, rule, days, checked_on, source_url, confidence)` and show "проверьте на официальном сайте" in the UI. **Never show a number nobody read on an official page.** The MFA site (mid.ru) didn't load from our tools, so all of this is secondary:

| Country | What sources say | Status |
|---|---|---|
| Thailand | Visa-free, but **30 or 60 days** depending on the source. Arrival card TDAC since 1 May 2025 | Sources conflict, confirm on the Thai MFA site |
| Vietnam | 45 days visa-free, reportedly until 14 Mar 2028 | Secondary |
| China | Visa-free trial from 15 Sep 2025, reportedly until autumn 2026 | **Status today unknown** |
| Egypt, UAE, Indonesia (Bali) | Visa-free or visa on arrival in older tables | Unconfirmed for 2026 |
| Turkey, Georgia, Armenia, Abkhazia, Belarus, Uzbekistan, Kazakhstan, Cuba, Sri Lanka, Maldives | Not checked | To do |
| Domestic | No visa; some border zones need a permit | To do |

The **Passport Index dataset** (MIT) is a fine starting grid, but the repo was archived on 12 Jan 2025. [Repo](https://github.com/ilyankou/passport-index-dataset) (verified)

### Money
- **CBR daily XML:** `https://www.cbr.ru/scripts/XML_daily.asp?date_req=25/10/2026` (USD is `R01235`). Fetch at runtime and keep a dated fallback rate in the seed. No JSON endpoint is documented. [CBR XML](https://www.cbr.ru/development/SXML/) (verified)
- **Cards abroad:** Mir acceptance has shrunk to a few banks per country, and Belarus is the clear exception. The agent should say «возьмите наличные или карту банка, которая работает за границей», not promise a card works (secondary).

### Events (optional)
- **KudaGo API v1.4** (Russian cities): the endpoints are listed, but whether it still works in 2026 and whether it needs a key are unverified. Test it live first. [KudaGo API](https://kudago.com/public-api/v1.4/)

## Check by hand before we rely on it

1. fedstat.ru hotel price and occupancy tables by region and month (our best real price anchor).
2. Travelpayouts terms: can we store and show cached prices, and do hotel endpoints still work.
3. Yandex Schedules daily limit, in the developer cabinet.
4. Copernicus Marine SST product licence, or NOAA OISST.
5. Visa rules, one official page per country (Thailand days, China after autumn 2026).
6. Hotel Booking Demand licence on its host page.
7. The Russian accommodation register and data.mos.ru: real hotel lists, if they're downloadable.
8. Nager.Date licence; KudaGo liveness.
