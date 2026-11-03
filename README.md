# FINN

A mobile-first financial investment agent. Two modes: it tells you what changed
in your portfolio (push), and it analyses any NSE company on demand (pull).

Built for the ENAM Holdings AI Engineer Build Challenge.

---

## The idea

An investor does not have an information problem. They have a filtering
problem. Sixty filings land overnight and four of them matter.

So the product is the filter, and the design makes the filtering visible: the
home screen opens with a plain sentence — *"4 things matter since yesterday"* —
and on a quiet day it says so instead of manufacturing headlines to fill the
screen. Materiality is carried by contrast and by the weight of each row's left
rule, not by badges. Routine filings are collapsed behind a count, never
hidden: showing how much was filtered out is what makes the filtering
trustworthy.

## Running it

```bash
cp .env.example .env     # add one API key; everything else has a default
make up                  # db + api + web
make ingest              # populate the digest
```

* App — http://localhost:3000 (open it on a phone, or in a 390px viewport)
* API docs — http://localhost:8000/docs

Without an API key it still runs. `LLM_PROVIDER=null` gives you rules-based
classification and the full ranking engine, just no summaries or extraction.

```bash
make test        # 46 backend tests, no database or network needed
make dev-api     # uvicorn with reload
make dev-web     # next dev
```

## Architecture

```
ingest (nightly)                     api (read-only, instant)
┌──────────────────────────┐         ┌────────────────────────┐
│ prices    yfinance EOD   │         │ /digest    ranked feed │
│ filings   NSE → BSE      │  ────►  │ /research  pull        │
│ documents screener.in    │   SQL   │ /alert-rules  config   │
│ classify  rules → LLM    │         │ /admin     usage, runs │
│ score     + market move  │         └────────────────────────┘
│ enrich    results, bios  │
│ alerts    thresholds     │
└──────────────────────────┘
```

Everything expensive happens in ingest, so the app opens instantly on a phone.
The one exception is a pull on an unknown ticker, which runs the pipeline live
— and the UI narrates the real steps rather than showing a spinner.

### Ranking

```
score = category_weight × materiality × recency_decay
      × (1 + market_corroboration) × size_factor × ownership
```

The interesting term is **market corroboration**. A press release that landed
on a day the stock moved 6% on triple volume is a different object from the
same release on a flat day. Price action is the market's own vote on
materiality, and it is the only input here the company does not control.

Routine status is judged on *un-decayed* substance, so a genuinely material
filing never quietly demotes itself into the collapsed drawer after two days.

### Promised vs delivered

The centrepiece of the pull side, and the thing the brief calls out as the
difference between summarising management and analysing them.

Two passes, deliberately separate because they have different lifetimes:

1. **Extract** — read four quarters of transcripts, pull out commitments that
   can later be marked right or wrong. Vague optimism is discarded at the
   prompt and again in code: a claim with neither a number nor an unambiguous
   direction never reaches the database. A transcript never changes, so this
   caches forever.
2. **Adjudicate** — compare each commitment against what the company actually
   reported. Verdicts move from `too_early` to `met`/`missed` as later quarters
   land, so this re-runs.

Whether a horizon has elapsed is decided **in code**, not by the model.
Marking an unfinished quarter as "missed" is the one error that would make the
product actively misleading, so it is not left to a prompt.

### Model routing

Three tiers, chosen per constraint rather than per task:

| Tier | Used for | Why |
|---|---|---|
| Regex rules | First-pass classification | Free; handles most of the feed |
| Cheap model | Residual classification, summaries, guidance extraction | High throughput, batched 20 subjects per call |
| Strong model | Results numbers, promise adjudication | The only genuinely hard reasoning |

Plus: a content-hash cache on every call (a re-run after a crash costs
nothing), a keyword prefilter that discards 60–75% of a transcript before any
token reaches a model, a concurrency semaphore sized for free-tier rate limits,
and per-call token accounting in `llm_usage`.

```bash
docker compose exec api python -m app.cli usage
```

### Primary sources only

The pull side reads annual reports and concall transcripts. No broker notes, no
news, and the prompts explicitly forbid the model from drawing on what it knows
about the company from elsewhere. Where the documents do not support an answer,
the UI shows a gap rather than a guess. Push-side enrichment — a background on
an incoming CFO — is a different thing and is allowed.

## Decisions worth defending

**Responsive web, not Expo.** The brief lists it. A grader opens a URL and it
works; TestFlight review and Expo Go install are two ways for a demo to fail in
someone else's hands. It ships with a manifest and safe-area insets, so Add to
Home Screen gives a real app shell.

**Hybrid data mode.** NSE throttles aggressively and 403s without a cookie
handshake. Every source degrades to a captured fixture rather than to an empty
screen. `DATA_MODE=live` disables the fallback if you want to see it fail
loudly.

**Dedup excludes the timestamp.** The same corporate event arrives from NSE and
BSE, gets republished with corrected times, and is often followed by its own
attachment as a separate row. The hash keys on company + normalised subject +
date, with boilerplate ("Intimation of", "under Regulation 30") stripped first.

**Nulls, not guesses.** `pct_change` refuses to compute across a sign flip
(loss → profit) or a near-zero base, because both produce numbers that are
arithmetically fine and financially meaningless. The UI renders those as "n.m."

**Fiscal quarters are a tested primitive.** Indian companies run April–March,
so Q1 FY27 is Apr–Jun 2026 and its QoQ comparator is Q4 FY26. Getting this
wrong silently corrupts every comparison in the product.

## Deliberately left out

Portfolio P&L and position tracking; intraday data; six of the eight pull
outputs; auth and multi-user; real OS push notifications (alerts are in-app);
news and broker integration, which the brief rules out on the pull side anyway.

Thin and working beat broad and broken, so the budget went to one push
workflow and one pull workflow done properly.

## Where it goes next

Nightly re-adjudication so a promise flips to `met` the morning its quarter
reports. Per-user portfolios. A delivery-rate track record per management team
across companies — the natural extension of promised-vs-delivered, and the
thing that would actually change a position. Real push notifications, which is
where native starts to earn its cost.

## Layout

```
backend/app/
  core/          config, logging, exceptions
  db/            models, session
  llm/           providers, client, cache, prompts
  services/
    ingest/      prices, announcements, fundamentals, runner
    classification/  taxonomy, rules, classifier
    ranking/     scorer
    analysis/    enrichment, guidance, research
    alerts/      evaluator
  api/routes/    digest, research, alerts, admin
  utils/         dates, numbers, text, http, pdf
web/
  app/           today, research, settings
  components/    digest, research, shared
  lib/           api client, formatters, hooks
```
