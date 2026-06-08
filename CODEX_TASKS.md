# CODEX_TASKS.md — engineering work to hand to Codex

> Claude (the trading brain + architect) writes the specs here. **Codex** implements
> them on a branch and opens a PR for Claude to review and merge. This keeps Claude
> in charge of trading judgment while offloading the grunt engineering to the flat-rate
> ChatGPT/Codex subscription — and it keeps Claude's subscription-token budget for the
> actual decisions.
>
> **Ground rules for every task in this file:**
> - Match the existing style of the file you touch. `candidates.py` is **pure Python
>   stdlib** (urllib, json) — **no `pip install`, no new dependencies.** The brain
>   workflow runs it with `python candidates.py` and no requirements step.
> - **Never let a data fetch break the run.** Every new source must be wrapped in its
>   own `try/except Exception` that prints a `(warn) ...` line and no-ops — exactly
>   like `_fetch_movers` / `_fetch_leading` already do. A dead endpoint must degrade
>   gracefully (worst case: those rows just don't appear this run).
> - Reuse the existing helpers: `_http_json(url, ...)` for GET-with-retry and
>   `_merge_candidate(seen, sym, ...)` to add/merge a candidate (it accumulates a
>   `signals` list and a `catalyst` dict — you do NOT need to touch serialization;
>   `_slim_row` already passes through any non-null field).
> - Open a PR; do **not** push to `main`. Claude reviews before merge.

---

## TASK 1 — Add a TRADING HALTS / RESUMPTIONS feed to `candidates.py`

**Why:** Lifting halt + resume data into the deterministic funnel lets the brain stop
spending a live web search on it every run (BRAIN.md STEP 1, search #1). LULD halts and
their resumptions often precede the biggest small-cap moves — catching the *resume* is
a real edge.

**Source (free, no key):** Nasdaq Trader trading-halts feed —
`http://www.nasdaqtrader.com/rss.aspx?feed=tradehalts` (RSS/XML). Each item has an
issue symbol, halt date/time, resumption date/time (often blank until set), and a
reason code (e.g. `LUDP` volatility pause, `T1`, `T12`, `H10`). Parse the XML with
stdlib `xml.etree.ElementTree` (the feed namespaces its fields — handle that).

**Implement:**
- A `_fetch_halts(seen: dict) -> None` following the `_fetch_movers` pattern.
- Tag each row `signal="halt_resume"`, and attach a `catalyst` dict:
  `{"halt_reason": <code>, "halt_time": <iso>, "resume_time": <iso or null>,
    "source": "nasdaqtrader", "published_utc": <iso of the halt/resume event>}`.
- Only include **today's** events (UTC), and prefer names with a resumption time set
  or a recent halt — drop anything older than ~1 trading day. Add a knob
  `MAX_HALTS = 60` to cap how many rows you add.
- Use `_merge_candidate` so a halted name that's ALSO a mover accumulates both tags.

**Wire it in:** call `_fetch_halts(seen)` inside `fetch_fmp_candidates()`, right after
`_fetch_leading(seen)`. It needs no API key, so it can run whenever (not gated on
`FMP_API_KEY`).

---

## TASK 2 — Add a fresh SEC 8-K filings feed to `candidates.py`

**Why:** Replaces BRAIN.md STEP 1 search #2 (fresh 8-Ks / material news). An 8-K is the
form companies file for material events (new contracts, M&A, offerings, executive
changes) — the freshest catalysts, often before the stock moves.

**Sources (free, no key — but SEC REQUIRES a descriptive `User-Agent` header on every
request, e.g. `schwab-trader/1.0 (you@example.com)`; SEC rate-limits to ~10
req/s, so make few calls):**
- Recent 8-K filings (Atom): `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=100&output=atom`
  — gives company name, **CIK**, filing datetime, and a link per filing.
- CIK → ticker map: `https://www.sec.gov/files/company_tickers.json` (one object per
  company with `cik_str`, `ticker`, `title`). Fetch once per run and build a
  `{cik: ticker}` dict; cache in-process. (CIKs are zero-padded to 10 digits in the
  Atom feed — normalize before matching.)

**Implement:**
- `_fetch_sec_8k(seen: dict) -> None`, same defensive pattern. Pass the SEC
  `User-Agent` header through `_http_json` (it already accepts a `headers` kwarg).
- For each recent 8-K whose CIK maps to a known ticker, `_merge_candidate` with
  `signal="sec_8k"` and `catalyst`:
  `{"headline": <filing title>, "form": "8-K", "source": "sec_edgar",
    "published_utc": <filing datetime iso>, "url": <filing link>}`.
- Only **today's / last-few-hours** filings (UTC). Add knobs `MAX_8K = 80` and reuse
  the `MIN_SHARE_PRICE` floor only if a price is known (the SEC feed has no price — so
  these rows may be price-less; that's fine, the brain reads the catalyst and the bot
  enforces the $2 floor at execution).
- Do NOT add the same filing twice; dedupe by (ticker, filing url).

**Wire it in:** call `_fetch_sec_8k(seen)` in `fetch_fmp_candidates()` after
`_fetch_halts(seen)`.

---

## After BOTH tasks land — update the docs (same PR or a follow-up)

- In `BRAIN.md` STEP 1, add two bullets to the tag list (next to `mover` /
  `earnings_soon` / `news_smallcap` / `news_bullish`):
  - `halt_resume` — a stock halted/resuming today (catch the resume).
  - `sec_8k` — filed a material 8-K in the last few hours (read the headline:
    contract win = bullish, dilutive offering = bearish).
- In `BRAIN.md` STEP 1, the "Targeted web search" block already says searches #1
  (halts) and #2 (8-Ks) should be **dropped** once these tags exist in the file —
  do that: remove those two numbered searches, leaving only #3 (sympathy) + the
  optional finalist-verification slot. That takes the routine to ~1 web search/run.

## Acceptance criteria
- `python candidates.py` runs clean with network access and `signals/candidates.json`
  now contains some `halt_resume` and/or `sec_8k` rows (when the market has any today),
  and `signal_counts` tallies them.
- With **no** network (or a dead endpoint), `python candidates.py` still exits 0 and
  writes a valid file — the new sources just no-op with a `(warn)` line.
- Output stays valid compact JSON; no new pip dependencies; no changes to how the
  trader (`bot.py`) reads anything.
