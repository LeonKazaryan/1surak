# 05: Plan, checklists, pitch

All times are MSK (UTC+3). For Astana (UTC+5), add 2 hours.

## Day by day

| Day | Goal by end of day | Done when |
|---|---|---|
| **Sat 24 Oct** (today) | Track confirmed, org invite accepted, repo cloned. Stack and roles decided. Skeleton: `docker compose up` → UI on :8080, `/health`, CI build | A teammate on another laptop clones the repo and sees the empty UI |
| **Sun 25 Oct**: expert day | Ask the expert questions (below). Agent loop with tool calling against seed data. Destination catalogue + climate/sea snapshot | The flagship query returns 3 grounded destinations with reasons |
| **Mon 26 Oct** | Flights, trains, hotels, transfer tools. TripState. Connection validator. Cart + mock checkout. **The whole journey works end-to-end, however ugly** | The flagship query reaches a booking confirmation |
| **Tue 27 Oct**: expert day | Show experts the working journey and write down every remark. Trip board UI, why/gave-up/risk cards, replan with a diff | «а если на два дня позже?» shows a correct diff |
| **Wed 28 Oct** | Eval set + `make eval`. Hotel fit, memory, post-purchase basics, responsive layout. README, screenshots, video. **Fresh-clone test on a clean machine. Tag rehearsal** | README checklist below all green |
| **Thu 29 Oct**, by **08:00** | Final push, then `git tag submission && git push origin submission`. Video link in the README, checked in incognito | The tag is visible on GitHub before 10:00 |
| Thu 29 Oct after 19:00 | Finalist announcement. If we're in: rehearse the pitch 3× with a timer | |
| **Fri 30 Oct 17:00** | Pitch: 5 + 5 min | |

**Freeze rule:** after 28 Oct 18:00 no new features, only fixes, README work and the video.

## Roles (for 3–5 people, adjust to the team)

| Role | Owns |
|---|---|
| Agent lead | The LLM loop, prompts, TripState, the replan logic |
| Tools / data | Seed snapshots, tool functions, the validator, the eval set |
| Frontend | The trip board, chat, streaming, mobile layout |
| DevOps / QA | Docker, CI, README, fresh-clone tests, `make eval` runs |
| Product / pitch | User flows, copy in Russian, the video, the pitch, expert questions |

## Questions for the experts (25 Oct), most important first

1. **LLM keys at judging time.** Will jurors put their own key into `.env`? Which providers or base URLs can they reach? Or must we ship a key / deployed instance? What happens if the key is missing?
2. Do the jury's unseen queries assume departure **from Russia**, and from which city by default?
3. Are the **10 finalists per track or overall**?
4. What weight does the **local run** carry against the video and the live demo? Do they test our deployed URL or only localhost?
5. Is a deployed demo link allowed for the live part, given limited time at the pitch?
6. Do they prefer a web UI or a messenger bot for the "mobile" extra?
7. How deep should post-purchase go to count?
8. Any preferred response language or tone (formal «вы»)?

Write the answers into this file.

## Submission checklist (from the tech rules)

- [ ] Repo is in the `ostrovok-hackathon-2026` org, on the main branch.
- [ ] `README.md` follows the official template: one-line description, **video link**, quick start (`git clone` → `cp .env.example .env` → `docker compose up --build` → `localhost:8080`), resources, dependencies, env vars with defaults, seeding, routes (`/`, `/health`), test user.
- [ ] README also has **"Task coverage"**: each of the 6 main tasks and 4 extras → ✅ plus where to see it (screenshot / route). This is for the LLM pre-screen and for tired jurors.
- [ ] README has a **"Data: real vs mock"** table and the **eval metrics table**.
- [ ] `docker-compose.yml` in the root, ports `8080:8080`, `env_file`, `healthcheck`, `depends_on` with `condition: service_healthy`.
- [ ] `Dockerfile` is multi-stage, runs as non-root, pins its base image versions, sets `platform: linux/amd64`.
- [ ] `.env.example` lists every variable with a safe default, and **no real secrets** are in git history.
- [ ] Seed data is committed and loads automatically on start (no manual step).
- [ ] Logs go to stdout; `docker compose logs app` shows the reason for any failure.
- [ ] A fresh clone on a different machine reaches a working UI in ≤10 min.
- [ ] The video is ≤5 min, publicly viewable, checked in incognito.
- [ ] Nice to have: a Makefile (`make up/down/seed/eval`), CI (docker build + lint + eval smoke), a deployed URL.
- [ ] The `submission` tag is on the last main commit, pushed before 10:00 MSK on 29 Oct.

## Pitch: 5 minutes

| Time | Content |
|---|---|
| 0:00–0:30 | Problem in one line plus the three stakeholders. "One message → whole trip bought." |
| 0:30–3:15 | **Live demo** of the flagship query: chips → destinations with the excluded ones → hotel comparison → timeline with a caught connection problem → cart → checkout. Then one replan: «а если на два дня позже?» → diff |
| 3:15–4:15 | How it works: one architecture slide (LLM decides / code computes), the eval numbers, the real-vs-mock table |
| 4:15–5:00 | Value for Ostrovok (bundle = average check, fewer drop-offs), for the hotel (fit = fewer cancellations), and what we'd build next |

Backup: if the live demo hangs for more than 10 s, switch to the recorded video at the same timestamp without comment.

For the Q&A, prepare answers to the table in [03-jury-lens.md](./03-jury-lens.md#likely-qa-questions-and-how-we-answer-them).

## Video (mandatory, 3–5 min)

Same story as the pitch, recorded from `localhost:8080` after a fresh `docker compose up`. Show the terminal command at the start, because it proves it runs locally. Add Russian captions or a voice-over, and show at least 2 different queries plus one replan.
