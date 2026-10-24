# Hackathon rules and timeline: the parts that matter

Taken from [the hackathon site](https://ostrovok.tech/hackathon/) and the official rules PDF ([local copy](./hackathon-rules.pdf), [original](https://ostrovok.tech/hackathon/docs/rules.pdf)). The PDF still carries some 2024 typos in its dates. Where the site and the PDF disagree, go by the site timeline.

## Timeline (Moscow time, UTC+3)

| Date | Day | What happens |
|---|---|---|
| 23 Oct | Fri | Opening (online) and a talk on Ostrovok's tech internals |
| 24 Oct | Sat | Work on tasks |
| 25 Oct | Sun | **Discussing tasks with experts** |
| 26 Oct | Mon | Work on tasks |
| 27 Oct | Tue | **Discussing tasks with experts** |
| 28 Oct | Wed | Work on tasks |
| **29 Oct 10:00** | Thu | **Submissions close** (rules 3.9). Git tag `submission` goes on the last commit of the main branch |
| 29 Oct 10:00 → 30 Oct 12:00 | | Jury scores *every* submission and picks **up to 10** finalists (the rules don't say whether that's per track or overall) |
| 29 Oct after 19:00 | Thu | Finalists announced |
| **30 Oct 17:00–19:00** | Fri | **Final pitch: 5 min presentation + 5 min jury Q&A.** The jury may revise scores based on the pitch |
| 30 Oct after 19:30 | Fri | Award ceremony (online) |

Astana is UTC+5, so 10:00 MSK is 12:00 Astana time and 17:00 MSK is 19:00 Astana time.

## Prizes (rules 4.2)

Each track has its own podium. The amounts are paid **after tax**.

| Place | Amount |
|---|---|
| 1st | 250 000 ₽ |
| 2nd | 150 000 ₽ |
| 3rd | 100 000 ₽ |

A team splits a prize: either one member receives all of it, or it's divided equally. To get paid you need a ruble account in a Russian or a European bank (rules 4.6).

## Judging (rules 3.7–3.9)

- The criteria "are formed in closed expert sessions" and are **not published** (3.8). We reverse-engineer them in [03-jury-lens.md](../03-jury-lens.md).
- Two stages: first every repo is scored, then the top ≤10 pitch live and can be re-scored.
- Experts named on the site: Владимир Симонов (Senior Engineering Manager), Галина Ревина (Senior Project Manager), Михаил Решетняк (Team Lead). The rules say only that the jury is "representatives of the organizer, approved by the organizer". So these three are likely judges, but that isn't confirmed.
- How the last edition ran, per [tproger](https://tproger.ru/articles/go--llm-i-1-4-mln-ohvata--kak-ostrovok-delaet-edinstvennyj-regul): **an LLM pre-screened submissions and dropped empty or raw ones**. After that, jurors judged "technical and product effectiveness". 18 experts were involved, and 460 teams took part.

## Rules that can hurt us

| Rule | What it means for us |
|---|---|
| 6.5(4)–(5): no third-party images, personal data or IP | Don't scrape hotel photos from Ostrovok or Booking. Use licensed images with attribution (Wikimedia, Unsplash) or none. OSM data needs an attribution line |
| 6.6: don't use organizer resources for unrelated purposes | Don't scrape ostrovok.ru |
| 7.1: don't share the task text with third parties without permission | Keep these docs inside the team repo |
| 7.3–7.4: **the exclusive rights to the submitted solution pass to Ostrovok** | Don't put in code we can't give away (employer code, paid templates). Ostrovok may legally reuse our ideas, which is part of why they run this |
| 2.3: the organizer may advertise vacancies to participants | This doubles as hiring. Clean engineering gets noticed |
| 9.3: the rules can change; participants must re-read them daily | Watch the Telegram channel |

## Technical rules: a short version (full text in [technical-rules.md](./technical-rules.md))

- One repo per team, inside `github.com/orgs/ostrovok-hackathon-2026`.
- Required files: `README.md`, `docker-compose.yml`, `Dockerfile`(s), `.env.example`.
- Start command: `git clone` → `cp .env.example .env` → `docker compose up --build` → `http://localhost:8080`. **Nothing else may need installing by hand.** Startup should take ≤10 minutes on a normal laptop.
- The app listens on 8080 inside the container, published as `8080:8080`. It needs a `/health` route that returns `{"status":"ok"}` plus a compose healthcheck, and `depends_on` with healthchecks.
- Images: multi-stage build, run as non-root, pinned versions (no `latest`), `platform: linux/amd64` when building on Apple Silicon, logs to stdout, POSIX shell only.
- Large models go through an OpenAI-compatible API and never into git. Real secrets are never committed.
- A video screencast is **mandatory**. It must play in an incognito window (public link on Yandex.Disk, Google Drive or similar).
- **If the jury can't run it locally, they can't score it.**
- Nice to have: Makefile (`make up/down/seed`), a CI job that builds the Docker image and runs a linter, a deployed URL.
