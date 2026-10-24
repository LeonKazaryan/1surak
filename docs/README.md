# О! Хакатон 2026: team docs

Our thinking space for the Ostrovok hackathon, track **«О!дин запрос»**: an AI agent that turns one traveller message into a whole booked trip.

## The task in one paragraph

Build a working prototype of an AI agent that turns one vague message («к тёплому морю в ноябре, недорого, с ребёнком, без долгих перелётов») into a whole trip: destination, flight or train, hotel and transfer. It has to explain every pick, check that the pieces fit together, cope with «а если на два дня позже?» without starting over, and walk the user to a fake checkout. Ostrovok gives **no data and no API**. We bring our own and have to say honestly what's mock. **At the final, the jury types queries we've never seen.**

## Key dates (MSK = UTC+3; Astana = MSK+2)

| When (MSK)                    | What                                                                                                                         |
|-------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| Sun 25 Oct                    | Expert Q&A #1. Take the questions in [05](./05-plan-and-checklists.md#questions-for-the-experts-25-oct-most-important-first) |
| Tue 27 Oct                    | Expert Q&A #2. Show them a working journey                                                                                   |
| **Thu 29 Oct 10:00**          | **Deadline:** `submission` tag on the last main commit, plus the video link in the README                                    |
| Thu 29 Oct after 19:00        | Finalists announced (up to 10)                                                                                               |
| **Fri 30 Oct 17:00 to 19:00** | Final pitch: 5 min + 5 min Q&A                                                                                               |

Prize per track: **250k / 150k / 100k ₽** (after tax).

## Read in this order

1. [01-task-explained.md](./01-task-explained.md): what is asked, in plain words, and how each part will be tested
2. [02-company-ostrovok.md](./02-company-ostrovok.md): who Ostrovok is, their market position, and what they really want from us
3. [03-jury-lens.md](./03-jury-lens.md): how judging works, our reconstructed scorecard, the instant-kill list
4. [04-winning-strategy.md](./04-winning-strategy.md): thesis, differentiators, scope, architecture, data sources, risks
5. [05-plan-and-checklists.md](./05-plan-and-checklists.md): day-by-day plan, expert questions, submission checklist, pitch
6. [06-test-queries.md](./06-test-queries.md): the golden query plus 40+ jury-style test queries (the seed for our evals)
7. [07-data-sources.md](./07-data-sources.md): every data source we researched, what to use, licences and links
8. [08-data-model.md](./08-data-model.md): how the facts join (place → cost → availability → time), quality rules, what we embed
9. [09-living-knowledge-base.md](./09-living-knowledge-base.md): the knowledge base the agent keeps growing with web search, its flexible entry shape, read and write rules

Original texts: [source/](./source/). The Russian copies are verbatim, except that dashes became plain punctuation. Everything outside `source/` is our analysis.

## Do these first

- [ ] **Confirm the track.** This folder is named `hack-odin-shag`, which matches «О!дин шаг до идеального отеля» (the middle/senior track). The brief analysed here is «О!дин запрос» (the junior track). They're different tasks.
- [ ] **Accept the GitHub org invite.** Membership in `ostrovok-hackathon-2026` is still *pending* for `SuWh1`, so the team repo isn't visible yet. Accept it from the email, or run `gh api -X PATCH user/memberships/orgs/ostrovok-hackathon-2026 -f state=active`.
- [ ] **Check the hackathon Telegram chat** for how the jury gets LLM access. This is our biggest fatal risk ([04](./04-winning-strategy.md#risk-register)).
- [ ] Clone the team repo and move this `docs/` folder into it.
