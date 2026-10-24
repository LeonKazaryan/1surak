# 03: Thinking as the jury

The official criteria are **not public** (rules 3.8). This file rebuilds them from the brief, the tech rules and how the last edition was judged. **The weights are our estimate.** Check them against what the experts say on 25 and 27 Oct.

## The funnel we have to get through

```
All submissions (tagged by 29 Oct 10:00 MSK)
   │  ① LLM pre-screen: drops empty or raw repos (how the last edition ran)
   ▼
   │  ② Jurors clone, run docker compose up, read the README, watch the video, try it
   │     (29 Oct 10:00 → 30 Oct 12:00, so roughly a day for all repos)
   ▼
Up to 10 finalists (announced 29 Oct after 19:00)
   │  ③ Live pitch: 5 min + 5 min Q&A, with unseen queries; scores can be revised
   ▼
Top 3 per track
```

What that means at each stage:

- **①** The screener reads text. The README must say plainly *what works*, map **each of the 6 tasks to where it's implemented**, and show screenshots and numbers. A thin README can get us cut by a machine.
- **②** A tired juror with many repos and a day. If `docker compose up --build` fails, or the app needs keys they don't have, **we get zero** («мы не сможем … проставить соответствующие баллы»). The first 60 seconds in the UI decide their impression.
- **③** The jury types queries we've never seen. Robustness and speed are on stage, live.

## Who is judging and what each of them looks for

The experts named on the site are Владимир Симонов (Senior Engineering Manager), Галина Ревина (Senior Project Manager) and Михаил Решетняк (Team Lead). The last edition had 18 experts, so expect more people than these three. Plan for these three *roles*:

| Role | What they reward | What makes them frown |
|---|---|---|
| **Engineering Manager** | Sound architecture: the LLM orchestrates and code computes. Guardrails, evals, graceful failures. Could this grow into a product? | Hallucinated prices or flights, a "prompt is the whole product" setup, nothing measured |
| **Project / Product Manager** | All 6 stages covered end-to-end, a clean demo story, the three user stories addressed, business sense (conversion, average check), honest scope | Half the journey missing, features nobody asked for, overclaiming |
| **Team Lead** | It runs first time. Clean repo, README, Docker done right (non-root, multi-stage, healthcheck), tests, readable code | "Works on my machine", committed secrets, a 3 GB image, chaotic commits |

## Our reconstructed scorecard (estimated weights)

| # | Criterion | Est. weight | What "excellent" looks like |
|---|---|---|---|
| 1 | **Full journey works**, from first message to fake purchase | 20% | Any reasonable query reaches checkout in ≤6 turns, with no dead ends |
| 2 | **Agent acts** (tools, state, plan), not chat retelling | 15% | Visible plan board, cart and timeline that the agent fills and changes |
| 3 | **Clarification quality** | 10% | At most 2 blocking questions, assumptions shown and editable |
| 4 | **Comparison and explanation**: why, what we gave up, risks | 15% | Criteria change with the user. Every pick has why, trade-off and risk. The user can correct the logic |
| 5 | **Connection checks** in the trip assembly | 10% | Deterministic timeline checks with clear warnings and fixes |
| 6 | **Replanning** without starting from scratch | 10% | A change touches only what it must, and we show "what changed" with the price delta |
| 7 | **Robustness on unseen queries** | 10% | Odd, impossible or adversarial inputs get sensible answers |
| 8 | **Tech compliance and engineering** | 5% | Clean `docker compose up`, README, `/health`, CI, tests |
| 9 | **Extras**: post-purchase, memory, metrics, mobile | 5% | Our eval numbers in the README; responsive UI; memory |
| | Pitch and video | Multiplier | A clear 5-minute story; quick, honest answers in Q&A |

## Instant-kill list (any one of these and we're out)

- [ ] `docker compose up --build` fails on a clean machine, on amd64, or needs an extra manual step.
- [ ] The app won't work without a secret key the jury doesn't have, and the README doesn't say so up front.
- [ ] The agent **invents** hotels, flights, prices or times that aren't in our data.
- [ ] The journey stops before checkout, or replanning throws the old plan away.
- [ ] Mock data passed off as real.
- [ ] No video, or a video that doesn't play in incognito.
- [ ] No `submission` tag, or the tag was set after 10:00 MSK.
- [ ] More than 20 seconds of silence before the first answer during the live demo.

## What makes a juror remember us

1. **The plan changes in front of them.** They say «а если на два дня позже?», and the timeline shifts, one flight swaps, the hotel stays, and a diff reads "+6 400 ₽: перелёт дороже, ранний заезд больше не нужен".
2. **The agent catches a trap they planted.** "You land at 23:40 and reception closes at 23:00. I added a transfer and pre-paid late check-in. Or take the 14:10 flight for +3 200 ₽?"
3. **The agent says no, honestly.** «Мальдивы на неделю за 30 000 на двоих» → "Not realistic, flights alone are from ~X ₽. Here's the warmest sea within your budget: …"
4. **Numbers from our own evals.** One slide: "On 40 test queries: 92% reached checkout, 1.2 questions on average, 7 s to the first recommendation, 0 connection errors."
5. **The hotel's side.** «Этот отель только для взрослых, поэтому я его исключил».

## Likely Q&A questions and how we answer them

| Question | Our answer should show |
|---|---|
| "What's real data and what's mock?" | A precise source table (we have one), with provenance shown in the UI |
| "How do you stop hallucinated prices?" | The LLM can only quote what tools return. The validator rejects plans that cite IDs missing from the data |
| "What if the LLM is down or slow?" | Timeouts, a retry, a fallback model, streaming progress |
| "How does replanning work without starting over?" | The plan is structured state. A change invalidates only the dependent parts |
| "How do you know it works on queries you haven't seen?" | The eval set, its metrics, and how we built it (categories in [06-test-queries.md](./06-test-queries.md)) |
| "What would it take to put this in production at Ostrovok?" | Swap the mock tools for internal APIs behind the same tool interface, plus A/B testing on the conversion metrics |
| "How much does a session cost?" | Tokens per session × the model's price. Measure it in evals |
| "Why this model / stack?" | Tool-calling quality vs. latency vs. cost, with one number for each |
