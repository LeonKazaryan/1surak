# 02: Who is giving the task, and what they actually want

## Ostrovok in 60 seconds

- **Ostrovok.ru** is a Russian online travel agency (OTA) focused on hotels, founded in 2010. The organizer's legal entity is ООО «Бронирование гостиниц», Moscow.
- The parent company is **Emerging Travel Group (ETG)**, which also runs the international B2B platform RateHawk. Ostrovok has its own B2B side for travel agents and business travel, and sells rail tickets to agents. Transfers are sold through partners.
- **It's the #2 OTA in Russia.** TravelLine puts it at 21.5% of online bookings in 2024, behind Yandex Travel at 29.2%. In early May 2026 it had 24.8% of OTA hotel sales. Yandex Travel together with Acase holds 34.9% ([kod.ru](https://kod.ru/yandex-ostrovok-sdelka), [Forbes](https://www.forbes.ru/tekhnologii/562862-ostrovok-poglosenia-kak-servis-bronirovania-otelej-okazalsa-vystavlen-na-prodazu)).
- Revenue was **9.7 bn ₽ in 2024 (+40% y/y)** across its two legal entities. Analysts describe the business as **loss-making**, in a travel market that is cooling.
- **It's up for sale.** Since late 2025 ETG has been selling the Russian business. In 2026 Yandex is the main candidate (Kommersant via kod.ru, May to July 2026). Only the **brand and hotel contracts** would change hands, and **the tech platform stays with ETG**. FAS approval is needed. We found no confirmation that the deal has closed.
- Its tech stack is Go and Python. The hackathon explicitly targets "Go- и Python-разработчиков, аналитиков и продактов".

> **Pitch rule:** don't mention the Yandex deal on stage. It's a sensitive topic for the people judging us. Treat it as background that explains their urgency, nothing more.

## The competitive picture: why *this* task, *now*

| Player | What they have in AI travel |
|---|---|
| **Yandex Travel** (#1) | Alice AI in «Моя поездка»: routes, must-see lists, seasonal events ([Yandex Journal](https://travel.yandex.ru/journal/alisa-ai-v-yandeks-puteshestviyah/)). In June 2026 Alice AI got an **AI-agent platform**. Only Yandex's own services use it so far ([Vedomosti](https://www.vedomosti.ru/technology/news/2026/06/29/1209627-dlya-sozdaniya-ii-agentov)) |
| **Otello** (2GIS) | Launched an AI assistant for planning trips, from picking a hotel to a day plan ([mail.ru](https://hi-tech.mail.ru/news/146386-servis-otello-zapustil-ii-assistenta-dlya-planirovaniya-puteshestvij/)) |
| **Ostrovok** | We found no public AI trip agent. This hackathon is where they're looking for one |

Ostrovok is **behind on AI** against its biggest rival. What's out there plans *sightseeing* or answers questions about *one hotel*. Nobody visibly takes a vague wish **all the way to a checked, bookable bundle**. That gap is exactly what the brief describes.

## Why Ostrovok runs a hackathon at all

From [tproger](https://tproger.ru/articles/go--llm-i-1-4-mln-ohvata--kak-ostrovok-delaet-edinstvennyj-regul), the hackathon site and the rules:

1. **Hiring and employer brand.** It's the only regular travel-tech hackathon in Russia. The last edition had 460 teams, 1.4 M people reached and direct hires. The rules reserve the right to advertise vacancies (2.3). This track is aimed at **juniors**, so they're scouting junior talent.
2. **Cheap R&D.** The rights to submitted solutions pass to Ostrovok (rules 7.3 and 7.4). 50+ teams prototyping "our AI agent" in a week is a market scan for them.
3. **Validating a product bet.** The brief reads like an internal product spec: stages, metrics, three stakeholders. They want to see which approaches hold up on real, messy queries.

## What they're really waiting for from us

Each point below is backed by a line from the brief.

| They want | Evidence in the brief | What it means for the build |
|---|---|---|
| **An agent that acts, not one that chats** | «Если агент просто пересказывает выдачу в чате, это не решение» | Tool calls change a visible plan, cart and timeline. Chat is the input, the plan board is the output |
| **Vague → concrete with few questions** | «задаёт только те уточняющие вопросы, без которых нельзя двигаться дальше. Анкета из 15 вопросов не подходит» | Assume and show the assumption, ask one or two blocking questions at most, every assumption can be edited |
| **Trust through transparency** | «повысить доверие к выбору за счёт прозрачных объяснений»; «понимать логику агента и мочь её поправить» | Each pick comes with why, what we gave up and the risks. The user's constraints sit visible on screen and can be edited |
| **Bundle selling** | «продавать поездку целиком, а не отдельный отель»; «росли конверсия, средний чек» | The cart holds hotel + transport + transfer + extras, with the basket total front and centre |
| **Correctness of logistics** | «успевает ли он на заселение, не съест ли трансфер всю экономию»; «проверяет состыковки» | A deterministic connection checker in code, not left to the LLM |
| **Incremental replanning** | «перестраивает план, а не начинает поиск с нуля» | Plan state is structured data, a change touches only the affected parts, and we show the diff |
| **Robustness on unknown inputs** | «запросы, которых вы заранее не видели» | Our own eval set, guardrails, graceful "this isn't possible, here's the closest option" |
| **Honesty** | «Если данные моковые, честно скажите об этом» | Data provenance badges in the UI, a data section in the README |
| **Hotel and guest fit** | Hotel user story: «меньше отмен и разочарованных отзывов» | A fit explanation plus honest "this hotel doesn't suit you" |
| **Measurable quality** (bonus) | Extra task 3 lists the exact metrics | An eval harness with a numbers table in the README and on a pitch slide |

## Context about their users that most teams will miss

Ostrovok's users mostly travel **from Russia**, which changes what "a good answer" means:

- Direct flights from Russia go to a limited set of countries: Turkey, Egypt, UAE, Thailand, Vietnam, China, the Caucasus, Central Asia and others. Most of the EU means a connection via Istanbul, Belgrade, Yerevan and similar hubs, **plus a Schengen visa**.
- Visa rules for a Russian passport are a real part of choosing a destination: visa-free, visa on arrival (Egypt) or a full visa. They belong among the reasons for a pick.
- Russian-issued cards mostly don't work abroad. A good agent mentions this for trips outside Russia.
- The Ostrovok homepage currently promotes Yerevan, Tbilisi, Batumi, Istanbul, Belgrade, Novi Sad, Minsk, Beijing, Guangzhou, Chengdu, Luxor, Kazan, Kaliningrad, Dagestan, Altai, St Petersburg and the Far East. That's a good hint for our destination catalogue.

An agent that answers «хочу в Париж на выходные» with honest visa and connection reasoning will stand out against one that cheerfully books a non-existent direct flight. (Check the specifics against current data before relying on them.)
