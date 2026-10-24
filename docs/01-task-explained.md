# 01: The task in plain words

Original text: [source/track-odin-zapros.md](./source/track-odin-zapros.md).

## The one-sentence version

Build an AI agent that takes **one vague message**, such as «хочу куда-нибудь к тёплому морю в ноябре, недорого, с ребёнком, без долгих перелётов», and **takes the person all the way to a (fake) purchase** of the whole trip: destination, transport, hotel and transfer. Along the way it explains every choice, checks that the pieces fit together, and rebuilds the plan when the user changes their mind.

## Why Ostrovok cares

Today their search wants exact inputs: city, dates, guests. People who don't know *where* to go drift off to social media and a dozen tabs, and many never come back. That's lost money at the very top of the funnel. Ostrovok mostly sells hotels one at a time. They want to **sell the trip as a whole**, because a bigger basket means a bigger average check, higher conversion and more repeat customers.

## The six things the agent must do (the "основные задачи")

Each row below covers four things: what the task says, what it really means, and how a juror will poke at it.

| #   | Task                               | What it really means                                                                                                                                                                        | How the jury will test it                                                                                                                                      |
| --- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Understand and clarify**         | Pull out explicit *and hidden* needs: budget, who's travelling, limits, mood. Ask **only the questions that block progress**. «Анкета из 15 вопросов не подходит»                           | They count the questions. Zero questions on a vague request is bad, and five or more before showing anything is worse. Do the inferred constraints make sense? |
| 2   | **Inspire and pick a destination** | If the user doesn't know where to go, suggest places **with reasons**: why this one, total cost, weather, travel time                                                                       | Are the reasons concrete (sea 26 °C, 4.5 h flight, ~X ₽) or fluff ("beautiful beaches")?                                                                       |
| 3   | **Find and compare**               | Hotels, flights or trains, and transfers, compared on **what matters to *this* user**: cancellation terms, meals, location, travel time, how the dates and times line up. Not just on price | Does the comparison change when the user is different (a family vs. a business traveller)?                                                                     |
| 4   | **Explain the choice**             | For every pick: why it fits, **what we gave up**, and **what the risks are**. The user must be able to **see the agent's logic and correct it**                                             | Can they say "no, the budget is wrong" and see the logic update?                                                                                               |
| 5   | **Assemble and buy**               | One plan and one cart. **Check the connections** (landing → transfer → check-in). Walk the user to checkout. Payment can be faked                                                           | They'll look for real timing checks, e.g. a 23:40 landing with a 14:00 check-in, or a return flight long after checkout                                        |
| 6   | **Rebuild the plan**               | «а если на два дня позже?», «бюджет меньше», «с нами едет собака» → **change the existing plan, don't start the search over**                                                               | They'll change one condition and watch whether everything else survives                                                                                        |

The core line of the brief: **«Если агент просто пересказывает выдачу в чате, это не решение. Нужен агент, который действует: уточняет, ищет, сравнивает, пересобирает план и доводит задачу до результата.»** A chatbot that only talks is an automatic loss.

## Optional extras (bonus points)

1. **After the purchase:** ask for early check-in, change the dates, send reminders, add a transfer to a hotel that's already booked.
2. **Memory:** remember preferences across sessions.
3. **Quality metrics:** our own set of test queries with measurements. The brief names four: share of scenarios completed, number of clarifying questions, time to first recommendation, connection errors.
4. **Mobile version** or a messenger bot.

## What they give us: nothing

- **No Ostrovok API, no MCP servers, no data.** We collect it all: data sources, tools, logic, UI.
- Open APIs, public datasets and **synthetic data are allowed**. If data is mocked, **we must say so honestly at the demo**.
- Booking and payment can be **simulated**.
- Any model, stack or architecture we like.

## What "done" means

> «Работающий прототип, в котором можно пройти весь путь от первого сообщения пользователя до оформленной (имитированной) покупки. **На защите жюри даст вашему агенту запросы, которых вы заранее не видели.**»

So the demo **can't be a script**. The agent has to cope with whatever the jury types, live, in under 5 minutes. That one sentence should drive most of our engineering choices: robustness beats features.

## The three user stories, read as success metrics

| Who | Wants | How we show it in the demo |
|---|---|---|
| Traveller | Describe the trip in their own words, get a clear plan, feel sure of the choice | Time from first message to first recommendation; explanation cards |
| Ostrovok | The user goes from idea to purchase *inside the service* and buys the *whole trip* | Full funnel to checkout; the cart bundles hotel + transport + transfer |
| Hotel | Gets recommended to guests it actually suits → fewer cancellations and bad reviews | A "why this hotel suits you" fit, plus honest mismatches («adults only, not for a 5-year-old») |

The hotel story is the one most teams will skip. It's cheap for us to cover and the jury will notice.

## Hard technical constraints (failing these can zero us)

See [source/hackathon-rules-and-timeline.md](./source/hackathon-rules-and-timeline.md#technical-rules-a-short-version-full-text-in-technical-rulesmd). In short: `docker compose up --build` on the jury's laptop, then `localhost:8080`, with no manual installs, a `/health` route, a mandatory video, and the `submission` tag by **29 Oct 10:00 MSK**.

## Note on the other track

«О!дин шаг до идеального отеля» is the middle/senior track: "reinvent the hotel booking experience with AI, data and new interface mechanics, from inspiration to payment and trip management." Its brief isn't in our sources. Our folder is called `hack-odin-shag`, so **confirm which track the team is registered in.** Everything here assumes «О!дин запрос».
