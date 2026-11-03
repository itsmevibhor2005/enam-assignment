# AI build history

A record of how FINN was built with an AI coding assistant (Claude), what was
delegated, what was decided by hand, and where the model got things wrong.

Credentials that appeared in the working session (a Gemini API key and a
Postgres password) are excluded from this document and were rotated.

---

## How the session was structured

Not one prompt. The build ran as a sequence of narrowing decisions, each of
which constrained the next:

1. **Read the brief, extract the actual ask.** Before any code, I had the
   model restate the problem in its own words so I could check it had the
   right one. The brief's own framing — *the scarce skill is filtering, not
   aggregating* — became the thing every later decision was tested against.
2. **Scope before stack.** What to build, and more importantly what to cut,
   given the deadline. Six of the eight pull outputs were dropped here.
3. **Stack, with reasons.** Python/FastAPI was near-forced by the data layer
   (`yfinance`, `pdfplumber`, `pandas`). Everything else was a real choice.
4. **Design direction.** Written out explicitly — palette, type, layout
   principle — before a single component, so the UI had a point of view
   rather than defaults.
5. **Backend bottom-up.** Utilities, then models, then services, then API.
   Each layer verified before the next was written.
6. **Frontend against real contracts.** Written after the API existed, typed
   against the actual Pydantic schemas.
7. **Deploy, debug, submit.**

## What was delegated vs decided

**Delegated to the model:** boilerplate across ~100 files, the regex rule
table for announcement classification, prompt drafting, React component
scaffolding, Docker and compose configuration.

**Decided by hand, with the model arguing the case:**

- *The product thesis.* Filtering is the product, so filtering must be
  visible. This drove the collapsed-routine drawer, the honest headline, and
  the rule-weight encoding of materiality.
- *The ranking formula,* specifically the market-corroboration term. The idea
  that same-day price action is the market's own vote on materiality — and the
  only input the company does not control — is the most opinionated thing in
  the codebase.
- *What to cut.* Six pull outputs, portfolio P&L, intraday, auth, real push
  notifications.
- *Responsive web over Expo.* The brief permits it, and a URL a grader can
  open beats a TestFlight review queue.

## Where the model was wrong, and how it was caught

This is the part worth reading. Four real bugs, all caught by tests and a
smoke run rather than by inspection:

**1. Word-order assumption in the ESOP rule.** The pattern assumed
`ESOP ... allotment`, but NSE files these as *"Allotment of equity shares
under Employee Stock Option Scheme"*. Every ESOP filing was escaping the rules
layer and being sent to the model as unclassified — the opposite of the
intended cost saving.

**2. Deduplication that did not deduplicate.** Boilerplate stripping left
orphaned filler words, so *"Intimation of acquisition of X"* and
*"Acquisition of X"* hashed differently. The exact duplicate the dedup exists
to prevent.

**3. Insider disclosures misfiled as litigation.** *"Disclosure under
Regulation 7(2) of SEBI (PIT) Regulations"* matched the litigation rule on the
bare word "SEBI". A routine promoter disclosure was being surfaced as
regulatory action against the company. Fixed by ordering insider-trading
patterns before litigation.

**4. The product lying in its first sentence.** The headline counted every
item displayed, so a day with ten middling filings announced *"10 things
matter"*. The whole premise is honest filtering; this was the one bug that
contradicted the product itself. Now the headline counts only what clears the
materiality bar.

The general lesson: the model wrote plausible code throughout. Plausible is
not correct, and the gap only showed under execution against realistic data.

## Guardrails built in because the model is in the loop at runtime too

FINN calls an LLM during ingest and research, so several design decisions
exist specifically to contain model error in production:

- **Horizon elapse is decided in code, not by the prompt.** Marking an
  unfinished quarter as "missed" is the one verdict error that would make the
  product actively misleading, so it is not left to inference.
- **Model output is treated as untrusted input.** Tolerant JSON parsing
  (fences, prose, trailing commas), schema validation, and a claim with
  neither a number nor an unambiguous direction never reaches the database.
- **Nulls are preserved, never filled.** A figure the extractor could not find
  renders as an em dash. A percentage that would be meaningless — a sign flip
  from loss to profit, a near-zero base — renders as "n.m." rather than a
  number.
- **Every pipeline step degrades independently.** One unreadable PDF or one
  malformed response does not abort an ingest run.
- **`LLM_PROVIDER=null` runs the whole product** on rules and the ranking
  engine alone. The test suite uses it; so would a demo on a dead network.

## Cost discipline

Three tiers chosen per constraint, not per task: regex rules (free, handles
most of the feed), a cheap model for bulk classification and guidance
extraction, a strong model only for results extraction and promise
adjudication. Plus content-hash caching on every call, a keyword prefilter
that drops the majority of each transcript before inference, batching of 20
classifications per request, and a concurrency semaphore sized for free-tier
rate limits. Per-call token accounting is exposed at `/api/admin/usage`.

## Verification

- 46 backend tests covering fiscal-quarter arithmetic, figure parsing,
  classification edges, ranking behaviour, dedup collisions, and tolerant JSON
  parsing. No database or network required.
- Full pipeline smoke run against seed data, end to end.
- Every module import-checked.
- Frontend production build verified before deploy.

## Deployment problems worth recording

- Railway injects `$PORT`; the Dockerfile had hard-coded 8000 and had to bind
  `${PORT:-8000}` in shell form.
- `DATABASE_URL` needed the `postgresql+psycopg://` driver prefix, which the
  platform's supplied value does not carry.
- `next/font/google` failed at build time fetching fonts; replaced with a
  stylesheet link so the build carries no network dependency.
- A first Railway attempt landed in the wrong project and built from the repo
  root; Root Directory had to be set to `backend` before the first build.

## Honest assessment

The assistant was most useful for volume — writing a structured ~100-file
codebase far faster than by hand — and for arguing both sides of a design
decision. It was least reliable exactly where domain knowledge was thin: the
specific phrasing of Indian exchange filings, which is where three of the four
bugs lived. Every one surfaced through execution, not review.
