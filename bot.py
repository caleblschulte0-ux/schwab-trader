"""Day-trade executor — simple marketable-limit entries + software-managed exits.

Why this design (learned the hard way on a small cash account):
  * BRACKET/OCO orders were repeatedly auto-canceled by Schwab on this account.
  * Buy limits priced off the brain's (stale, web-sourced) number sat BELOW the
    live ask and never filled.
So entries are now DEAD SIMPLE and priced off Schwab's LIVE quote:
  ENTRY  = plain BUY limit at (live ask * 1.002) -> marketable, fills now at the
           real price. DAY duration. No bracket.
  EXITS  = managed in software here (runs on a schedule): for each held position,
           if price >= the pick's take_profit or <= its stop_loss, SELL to close.
           Also honors a brain {"action":"SELL"} signal.

Ground truth: every run the bot writes the account's REAL positions to
signals/holdings.json. The brain reads that file to know what it actually owns.
The bot also builds signals/candidates.json — the brain's structured top-of-funnel.
It combines LAGGING movers (gainers/most-active/losers) with LEADING signals:
upcoming earnings (FMP) and stock news (Alpha Vantage). News tickers are cross-
referenced against a small-cap universe (Nasdaq's free public screener) to DISCOVER
small-caps that are in the news (not just annotate names we already had), so the
brain can position BEFORE a move. Each row is tagged with its reason(s).
A brain-written signals/watchlist.json lets the bot auto-enter on a price/date
trigger between brain runs (same guardrails); the bot only reads that file.

Risk rules still enforced in code (your one rule is safe):
  * BUY-only; we only ever SELL shares we already own (never short).
  * quantity * entry <= MAX_DOLLARS_PER_TRADE.
  * reject sub-$MIN_SHARE_PRICE penny stocks (pump/dump guard).
  * skip symbols already HELD, with an OPEN buy, OR bought in the last
    RECENT_BUY_COOLDOWN_MIN minutes (closes the settlement-lag double-buy gap);
    if orders can't be read, place NOTHING (fail safe).
  * don't chase (hard backstop): skip a BUY if live ask > limit_price * (1+MAX_SLIPPAGE).

DRY_RUN defaults to "true". Set a DRY_RUN repo variable to "false" to go live.

Secrets (GitHub Actions): SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN
Optional: SCHWAB_CALLBACK_URL, DRY_RUN, FMP_API_KEY (movers + earnings + small-cap
universe), ALPHA_API_KEY (stock news + small-cap-in-news discovery)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from schwab import SchwabAuth, SchwabClient
from schwab.models.generated.trading_models import Instruction, Duration

# ===== GUARDRAILS / KNOBS =====
MAX_DOLLARS_PER_TRADE = 65.00   # never spend more than this on one entry
MAX_SIGNAL_AGE_HOURS  = 18      # ignore a stale orders.json
MAX_SLIPPAGE          = 0.05    # skip a BUY if live ask is >5% above the pick's limit
MARKETABLE_BUFFER     = 0.002   # buy limit = live ask * (1 + this) so it fills now
ORDERS_FILE           = "signals/orders.json"
HOLDINGS_FILE         = "signals/holdings.json"
MIN_TP_OVER_ENTRY     = 0.005
MIN_STOP_UNDER_ENTRY  = 0.005
MIN_SHARE_PRICE       = 2.00    # hard floor: skip sub-$2 penny-stock pump/dump traps
RECENT_BUY_COOLDOWN_MIN = 60    # don't re-buy a symbol bought in the last hour
CANDIDATES_FILE       = "signals/candidates.json"
WATCHLIST_FILE        = "signals/watchlist.json"
FMP_BASE              = "https://financialmodelingprep.com/stable"
# --- leading-signal funnel (proactive: find names BEFORE they run) ---
EARNINGS_LOOKAHEAD_DAYS = 7     # enrich any candidate reporting within this window
EARNINGS_ADD_DAYS       = 7     # also ADD covered names reporting within this window
MAX_EARNINGS_ADD        = 80    # cap pre-earnings names added as fresh candidates
# --- stock-news funnel (Alpha Vantage News & Sentiment; free tier = 25 calls/day) ---
NEWS_BASE             = "https://www.alphavantage.co/query"
NEWS_DAILY_BUDGET     = 22      # max AV calls per UTC day (under the 25/day free cap)
NEWS_REFRESH_MIN      = 13      # min minutes between AV calls (dedupe rapid/manual runs)
NEWS_LIMIT            = 1000    # pull DEEP so small-caps in the long tail surface
NEWS_MIN_RELEVANCE    = 0.30    # ignore tickers only loosely mentioned in an article
NEWS_MIN_SENTIMENT    = 0.15    # bullish threshold for the (mega-cap) market-wide feed
NEWS_SMALLCAP_FLOOR   = -0.15   # small-caps: surface unless the coverage is clearly bearish
MAX_NEWS_SMALLCAP     = 150     # cap discovered small-cap-in-the-news names (wide funnel)
MAX_NEWS_BULLISH      = 25      # cap the (mostly large-cap) bullish market-wide names
# --- small-cap universe (Nasdaq's free public screener; DISCOVERs small-caps in the news) ---
NASDAQ_SCREENER_URL   = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true"
SMALLCAP_MAX_CAP      = 2_000_000_000   # "small cap" ceiling (~$2B)
SMALLCAP_MIN_CAP      = 50_000_000      # floor: skip nano-cap shells (~$50M)
# --- market regime (the macro tape the brain reads FIRST; FMP-sourced, throttled) ---
REGIME_REFRESH_MIN    = 25      # min minutes between regime refetches (the tape moves slowly)
REGIME_INDEXES        = ("SPY", "QQQ")  # ETF proxies for the broad-market trend
# --- watchlist (bot auto-enters when a brain-set trigger fires between runs) ---
MAX_WATCHLIST           = 12    # cap watch items (bounds per-symbol quote calls)
MAX_WATCHLIST_AGE_HOURS = 48    # ignore a watchlist file older than this (fail-safe)
# ==============================

APP_KEY       = os.environ["SCHWAB_APP_KEY"].strip()
APP_SECRET    = os.environ["SCHWAB_APP_SECRET"].strip()
REFRESH_TOKEN = os.environ["SCHWAB_REFRESH_TOKEN"].strip()
CALLBACK      = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1/").strip()
DRY_RUN       = os.environ.get("DRY_RUN", "true").strip().lower() != "false"
FMP_API_KEY   = os.environ.get("FMP_API_KEY", "").strip()
# Alpha Vantage stock-news key. Accept either name (the GitHub secret is ALPHA_API_KEY).
AV_API_KEY    = (os.environ.get("ALPHA_API_KEY") or os.environ.get("ALPHAVANTAGE_API_KEY", "")).strip()


def _http_json(url: str, timeout: int = 20, retries: int = 2, headers: dict | None = None):
    """GET JSON with a light retry on TRANSIENT failures only (connection blip /
    timeout / 5xx). A 4xx (FMP 402 Payment Required, 404, ...) is PERMANENT — re-raise
    immediately without retrying so we never waste the call budget hammering a dead
    endpoint. Raises the last error if every attempt fails (callers degrade gracefully).
    A malformed body (json) also propagates without retry (retrying won't fix it)."""
    import time
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers=headers or {})
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raise  # permanent (402/404/...) — don't retry, don't burn budget
            last_exc = exc  # 5xx: transient
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc  # network blip: transient
        if attempt < retries:
            time.sleep(0.5 * (2 ** attempt))  # 0.5s, then 1s backoff
    raise last_exc  # type: ignore[misc]


def _fmp_get(endpoint: str, params: str = "") -> list:
    """GET one FMP /stable endpoint -> list of rows (light retry on transient errors;
    no retry on 402/404). Returns [] if the body isn't a list. Raises on hard failure
    (callers wrap it so a dead endpoint just no-ops)."""
    sep = "&" if params else ""
    url = f"{FMP_BASE}/{endpoint}?{params}{sep}apikey={FMP_API_KEY}"
    data = _http_json(url, timeout=20)
    return data if isinstance(data, list) else []


def _merge_candidate(seen: dict, sym: str, *, name=None, price=None, pct=None,
                     exch=None, lst=None, signal=None, catalyst=None,
                     vol=None, mktcap=None) -> bool:
    """Add a candidate or merge into an existing one. The KEY behavior: when a
    symbol shows up from more than one source, we ACCUMULATE its reasons in a
    `signals` list instead of overwriting — so the brain can see that, e.g., a
    +4% mover ALSO reports earnings tomorrow. Returns True if newly added."""
    if not sym:
        return False
    row = seen.get(sym)
    if row is None:
        seen[sym] = {
            "symbol": sym, "name": name, "price": price, "pct_change": pct,
            "exchange": exch, "list": lst,
            "volume": vol, "market_cap": mktcap,
            "signal": signal, "signals": [signal] if signal else [],
        }
        if catalyst:
            seen[sym]["catalyst"] = catalyst
        return True
    # Merge: backfill any missing fields, accumulate the new reason.
    if name and not row.get("name"):
        row["name"] = name
    if price is not None and not row.get("price"):
        row["price"] = price
    if pct is not None and row.get("pct_change") is None:
        row["pct_change"] = pct
    if exch and not row.get("exchange"):
        row["exchange"] = exch
    if vol is not None and row.get("volume") is None:
        row["volume"] = vol
    if mktcap is not None and row.get("market_cap") is None:
        row["market_cap"] = mktcap
    if signal and signal not in row.get("signals", []):
        row.setdefault("signals", []).append(signal)
    if catalyst:
        row.setdefault("catalyst", {}).update(catalyst)
    return False


def _fetch_movers(seen: dict) -> None:
    """LAGGING funnel (unchanged from day one): names that ALREADY moved today."""
    lists = {"gainers": "biggest-gainers", "actives": "most-actives",
             "losers": "biggest-losers"}
    for label, ep in lists.items():
        try:
            rows = _fmp_get(ep)
            n = sum(_merge_candidate(
                seen, row.get("symbol"), name=row.get("name"), price=row.get("price"),
                pct=row.get("changesPercentage"), exch=row.get("exchange"),
                vol=row.get("volume"), lst=label, signal="mover") for row in rows)
            print(f"(fmp) {label}: +{n} new")
        except Exception as exc:  # noqa: BLE001 - never let data fetch break the run
            print(f"(warn) FMP {label} fetch failed: {exc}")


def _fetch_leading(seen: dict) -> None:
    """LEADING funnel (the proactive upgrade): UPCOMING EARNINGS so the brain can
    position BEFORE the report. (FMP's analyst grade/price-target feeds were dropped:
    grade-latest-news 404s and price-target-latest-news is 402 Payment Required on
    the free tier — analyst actions now reach the brain via the news feed + web
    search.) Isolated in try/except: a failed endpoint just no-ops.

    Two uses of the earnings calendar: (a) ENRICH any existing candidate that reports
    soon (a mover reporting tomorrow is high-priority); (b) ADD covered names
    reporting in the lookahead window that aren't on any list yet — "who's reporting
    soon", the pre-position pool."""
    try:
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=EARNINGS_LOOKAHEAD_DAYS)
        rows = _fmp_get("earnings-calendar", f"from={today}&to={end}")
        added = enriched = 0
        for row in rows:
            sym = row.get("symbol")
            raw = str(row.get("date", ""))[:10]
            try:
                edate = datetime.fromisoformat(raw).date()
            except ValueError:
                continue
            est = row.get("epsEstimated")
            cat = {"earnings_date": raw}
            if est is not None:
                cat["eps_estimate"] = est
            if sym in seen:
                _merge_candidate(seen, sym, signal="earnings_soon", catalyst=cat)
                enriched += 1
            elif (added < MAX_EARNINGS_ADD and edate <= today + timedelta(days=EARNINGS_ADD_DAYS)
                  and est is not None):  # epsEstimated => analyst-covered / liquid enough
                _merge_candidate(seen, sym, name=sym, lst="calendar",
                                 signal="earnings_soon", catalyst=cat)
                added += 1
        print(f"(fmp) earnings (next {EARNINGS_LOOKAHEAD_DAYS}d): enriched {enriched}, added {added} upcoming")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) FMP earnings-calendar failed (skipped): {exc}")


def _fetch_smallcap_universe() -> dict[str, dict]:
    """Map of SMALL-CAP symbol -> {market_cap, volume, price, pct} (market cap ~$50M-$2B,
    above our $2 floor) from Nasdaq's FREE public screener — one no-auth call covering
    the whole US market with real market caps AND volume. Two jobs: (a) DISCOVER which
    names in the news feed are small-caps, and (b) ENRICH them with cap/volume/price the
    news feed itself lacks (news rows otherwise arrive with only a headline). Returns
    {} on any failure (graceful — just disables small-cap tagging that run).
    (FMP's screener is 402 Payment Required on the free tier, so we don't use it.)"""
    def _num(v):
        try:
            return float(str(v).replace("$", "").replace(",", "").replace("%", "").strip() or 0)
        except (TypeError, ValueError):
            return None
    try:
        payload = _http_json(NASDAQ_SCREENER_URL, timeout=30,
                             headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        data = payload.get("data") or {}
        rows = data.get("rows") or (data.get("table") or {}).get("rows") or []
        universe: dict[str, dict] = {}
        for row in rows:
            sym = str(row.get("symbol", "")).strip().upper()
            cap, px = _num(row.get("marketCap")), _num(row.get("lastsale"))
            if cap is None or px is None:
                continue
            if sym and SMALLCAP_MIN_CAP <= cap <= SMALLCAP_MAX_CAP and px >= MIN_SHARE_PRICE:
                vol = _num(row.get("volume"))
                universe[sym] = {"market_cap": cap, "price": px,
                                 "volume": int(vol) if vol else None,
                                 "pct": _num(row.get("pctchange"))}
        print(f"(universe) small-cap symbols: {len(universe)}")
        return universe
    except Exception as exc:  # noqa: BLE001 - never let the universe fetch break the run
        print(f"(warn) small-cap universe fetch failed (skipped): {exc}")
        return {}


def _av_time_to_iso(t) -> str | None:
    """Alpha Vantage's time_published is 'YYYYMMDDTHHMMSS' (UTC). Return ISO 8601 so the
    brain can judge how FRESH a catalyst is (hot news = move may still be ahead; days-old
    news = likely already priced in). None if missing/unparseable."""
    if not t:
        return None
    try:
        return datetime.strptime(str(t), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _parse_av_feed(payload: dict) -> list[dict]:
    """Turn an Alpha Vantage NEWS_SENTIMENT response into one row per on-topic ticker
    (relevance-filtered, deduped to each ticker's most-recent mention; CRYPTO:/FOREX:
    pseudo-tickers skipped). Sentiment is NOT filtered here — the caller decides
    (small-caps surface on any non-bearish coverage; mega-caps need bullish)."""
    feed = payload.get("feed")
    if not isinstance(feed, list):
        # AV signals rate-limit / bad key via an Information/Note/Error message.
        note = payload.get("Information") or payload.get("Note") or payload.get("Error Message")
        if note:
            print(f"(news) AV said: {str(note)[:140]}")
        return []
    out: list[dict] = []
    picked: set[str] = set()
    for item in feed:
        title = item.get("title")
        src = item.get("source")
        published = _av_time_to_iso(item.get("time_published"))
        for ts in (item.get("ticker_sentiment") or []):
            sym = str(ts.get("ticker", "")).strip().upper()
            if not sym or ":" in sym or sym in picked:
                continue
            try:
                rel = float(ts.get("relevance_score", 0))
                sent = float(ts.get("ticker_sentiment_score", 0))
            except (TypeError, ValueError):
                continue
            if rel < NEWS_MIN_RELEVANCE:
                continue
            label = str(ts.get("ticker_sentiment_label", ""))
            picked.add(sym)
            out.append({"sym": sym, "sent": sent, "label": label,
                        "catalyst": {"headline": title, "sentiment": label,
                                     "sentiment_score": round(sent, 3), "source": src,
                                     "published_utc": published}})
    return out


def _carry_forward_news(seen: dict, prev: dict) -> int:
    """Re-add the previous run's news names (both small-cap and bullish) so the signal
    persists on throttled runs between actual Alpha Vantage calls."""
    carried = 0
    for row in prev.get("candidates", []):
        sigs = row.get("signals") or []
        tag = "news_smallcap" if "news_smallcap" in sigs else ("news_bullish" if "news_bullish" in sigs else None)
        if tag:
            _merge_candidate(seen, row.get("symbol"), name=row.get("name"),
                             price=row.get("price"), pct=row.get("pct_change"),
                             exch=row.get("exchange"), lst=row.get("list"),
                             vol=row.get("volume"), mktcap=row.get("market_cap"),
                             signal=tag, catalyst=row.get("catalyst"))
            carried += 1
    return carried


def _fetch_news(seen: dict, prev: dict, smallcap: dict[str, dict]) -> dict:
    """LEADING stock-news signal with small-cap DISCOVERY. One deep AV pull gives every
    ticker in the news; we then split it:
      * ticker in the small-cap universe + not clearly bearish -> `news_smallcap`
        (the names we want BROUGHT to us — small-caps in the news, even if not yet a
        mover), and
      * otherwise, bullish-leaning -> `news_bullish` (mostly mega-cap context).
    Throttled by a per-UTC-day counter (persisted in candidates.json) to stay under
    AV's free 25/day cap. Returns the news meta to persist. No-ops without a key."""
    today = datetime.now(timezone.utc).date().isoformat()
    meta = {"news_updated_utc": prev.get("news_updated_utc"),
            "news_calls_date": prev.get("news_calls_date"),
            "news_calls_today": prev.get("news_calls_today", 0) or 0}
    if not AV_API_KEY:
        return meta
    calls = meta["news_calls_today"] if meta["news_calls_date"] == today else 0  # reset on new day
    meta["news_calls_date"] = today
    last = _parse_dt(meta["news_updated_utc"])
    age_min = (datetime.now(timezone.utc) - last).total_seconds() / 60 if last else 1e9
    if calls >= NEWS_DAILY_BUDGET or age_min < NEWS_REFRESH_MIN:
        why = "daily budget reached" if calls >= NEWS_DAILY_BUDGET else f"{age_min:.0f}m < {NEWS_REFRESH_MIN}m"
        carried = _carry_forward_news(seen, prev)
        print(f"(news) throttled ({why}; {calls}/{NEWS_DAILY_BUDGET} today) — carried {carried} prior names")
        meta["news_calls_today"] = calls
        return meta
    try:
        import urllib.request
        url = f"{NEWS_BASE}?function=NEWS_SENTIMENT&sort=LATEST&limit={NEWS_LIMIT}&apikey={AV_API_KEY}"
        with urllib.request.urlopen(url, timeout=25) as r:
            payload = json.loads(r.read().decode("utf-8"))
        sc = bull = 0
        for row in _parse_av_feed(payload):
            sym, sent = row["sym"], row["sent"]
            if sym in smallcap and sent > NEWS_SMALLCAP_FLOOR and sc < MAX_NEWS_SMALLCAP:
                info = smallcap.get(sym) or {}
                _merge_candidate(seen, sym, signal="news_smallcap", lst="news",
                                 price=info.get("price"), pct=info.get("pct"),
                                 vol=info.get("volume"), mktcap=info.get("market_cap"),
                                 catalyst=row["catalyst"])
                sc += 1
            elif (sent >= NEWS_MIN_SENTIMENT or "Bull" in row["label"]) and bull < MAX_NEWS_BULLISH:
                _merge_candidate(seen, sym, signal="news_bullish", lst="news", catalyst=row["catalyst"])
                bull += 1
        meta["news_updated_utc"] = datetime.now(timezone.utc).isoformat()
        meta["news_calls_today"] = calls + 1
        print(f"(news) +{sc} small-cap-in-news, +{bull} bullish names ({meta['news_calls_today']}/{NEWS_DAILY_BUDGET} today)")
    except Exception as exc:  # noqa: BLE001 - never let news break the run
        print(f"(warn) news fetch failed: {exc}")
        _carry_forward_news(seen, prev)
        meta["news_calls_today"] = calls  # a failed call shouldn't burn the budget
    return meta


def _read_candidates() -> dict:
    """Previous candidates.json (for the news throttle / carry-forward). {} if none."""
    try:
        with open(CANDIDATES_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _write_candidates(seen: dict, news_meta: dict | None = None,
                      market: dict | None = None, market_utc: str | None = None) -> None:
    counts: dict[str, int] = {}
    for row in seen.values():
        for s in (row.get("signals") or ([row["signal"]] if row.get("signal") else [])):
            counts[s] = counts.get(s, 0) + 1
    data = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(seen),
        "signal_counts": counts,
        # Macro tape the brain reads first (omitted entirely if unavailable):
        **({"market": market} if market else {}),
        **({"market_updated_utc": market_utc} if market_utc else {}),
        # AV news throttle state (persisted across runs):
        **(news_meta or {}),
        "candidates": sorted(seen.values(), key=lambda x: x["symbol"]),
    }
    try:
        os.makedirs(os.path.dirname(CANDIDATES_FILE), exist_ok=True)
        with open(CANDIDATES_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        print(f"Wrote {CANDIDATES_FILE}: {len(seen)} candidates {counts}")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write candidates file: {exc}")


def _fmp_quote_one(symbol: str) -> dict | None:
    """One FMP quote row for a symbol (index ETF / ^VIX), or None on any failure. The
    `stable` quote body may be a list or a single dict; tolerate both. A 402/404 (paid/
    missing on the free tier) just returns None — the caller degrades to partial data."""
    try:
        data = _http_json(f"{FMP_BASE}/quote?symbol={symbol}&apikey={FMP_API_KEY}", timeout=15)
    except Exception:  # noqa: BLE001 - permanent or transient: caller degrades gracefully
        return None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict) and data:
        return data
    return None


def _fetch_sector_perf() -> list[dict]:
    """Best-effort sector-performance snapshot [{sector, pct}, ...] sorted hot->cold. The
    FMP path/shape varies and may be paid; every shape is tried in turn and on total
    failure we return [] (the brain simply won't see a sector tilt — no regression)."""
    today = datetime.now(timezone.utc).date().isoformat()
    for ep in (f"sector-performance-snapshot?date={today}", "sector-performance", "sectors-performance"):
        try:
            url = f"{FMP_BASE}/{ep}{'&' if '?' in ep else '?'}apikey={FMP_API_KEY}"
            data = _http_json(url, timeout=15)
        except Exception:  # noqa: BLE001
            continue
        rows = data if isinstance(data, list) else (
            data.get("sectorPerformance") if isinstance(data, dict) else None)
        if not isinstance(rows, list) or not rows:
            continue
        out: list[dict] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            name = r.get("sector")
            chg = r.get("changesPercentage", r.get("averageChange"))
            if name is None or chg is None:
                continue
            try:
                out.append({"sector": name, "pct": round(float(str(chg).replace("%", "").strip()), 2)})
            except (TypeError, ValueError):
                continue
        if out:
            out.sort(key=lambda x: x["pct"], reverse=True)
            return out
    return []


def _fetch_market_regime(prev: dict) -> tuple[dict, str | None]:
    """Top-level MACRO snapshot so the brain can read the tape BEFORE picking: index
    trend (SPY/QQQ %), a volatility read (VIX), the day's hot/cold sectors, and a
    conservative derived `tone`. All FMP-sourced (Alpha Vantage's daily budget is
    reserved for news) and THROTTLED to ~REGIME_REFRESH_MIN (the tape moves slowly) to
    protect the FMP call budget. Every sub-call is isolated — whatever is available is
    included; if everything fails the block is simply absent (zero regression). Returns
    (market_dict, market_updated_utc)."""
    if not FMP_API_KEY:
        return prev.get("market") or {}, prev.get("market_updated_utc")
    last = _parse_dt(prev.get("market_updated_utc"))
    age_min = (datetime.now(timezone.utc) - last).total_seconds() / 60 if last else 1e9
    if age_min < REGIME_REFRESH_MIN and prev.get("market"):
        print(f"(regime) throttled ({age_min:.0f}m < {REGIME_REFRESH_MIN}m) — reusing prior tape")
        return prev["market"], prev.get("market_updated_utc")

    market: dict = {}
    for sym in REGIME_INDEXES:  # broad-market trend via ETF proxies
        row = _fmp_quote_one(sym)
        if not row:
            continue
        pct = row.get("changesPercentage")
        if pct is None:
            pct = row.get("changePercentage")
        if pct is None:  # some feeds drop % after hours — derive it from price vs prior close
            price, prev = row.get("price"), row.get("previousClose")
            try:
                pct = (float(price) / float(prev) - 1.0) * 100.0 if price and prev else None
            except (TypeError, ValueError, ZeroDivisionError):
                pct = None
        if pct is not None:
            try:
                market[f"{sym.lower()}_pct"] = round(float(pct), 2)
            except (TypeError, ValueError):
                pass
    vix_row = _fmp_quote_one("%5EVIX") or _fmp_quote_one("VIXY")  # ^VIX (URL-encoded), ETF fallback
    vix_val = vix_row.get("price") if vix_row else None
    if vix_val is not None:
        try:
            market["vix"] = round(float(vix_val), 2)
        except (TypeError, ValueError):
            pass
    sectors = _fetch_sector_perf()
    if sectors:
        market["sectors"] = sectors

    spy, vix = market.get("spy_pct"), market.get("vix")  # conservative hint; the brain still judges
    if spy is not None or vix is not None:  # set a tone whenever we have ANY macro read
        if (spy is not None and spy <= -1.0) or (vix is not None and vix >= 25):
            market["tone"] = "risk_off"
        elif spy is not None and spy >= 0.3:
            market["tone"] = "risk_on"
        else:
            market["tone"] = "neutral"

    if not market:
        print("(regime) no macro data available this run (endpoints unavailable) — omitting tape")
        return prev.get("market") or {}, prev.get("market_updated_utc")
    print(f"(regime) tape: {market.get('tone','?')} | SPY {market.get('spy_pct','?')}% "
          f"QQQ {market.get('qqq_pct','?')}% VIX {market.get('vix','?')} | "
          f"{len(market.get('sectors', []))} sectors")
    return market, datetime.now(timezone.utc).isoformat()


def fetch_fmp_candidates() -> None:
    """Build the brain's structured top-of-funnel and write signals/candidates.json.
    Combines a LAGGING list (today's movers) with LEADING signals — upcoming earnings
    (FMP) and stock news (Alpha Vantage), the latter cross-referenced against a
    small-cap universe (Nasdaq's free screener) to DISCOVER small-caps in the news —
    so the brain can act BEFORE the move. Each source is keyed and isolated: missing keys / failed
    endpoints just no-op (worst case = today's movers, or an empty file). Throttles
    the AV news call to stay under its 25/day free cap."""
    if not (FMP_API_KEY or AV_API_KEY):
        print("(info) no data-source keys set — skipping candidate prefetch.")
        return
    prev = _read_candidates()
    seen: dict[str, dict] = {}
    if FMP_API_KEY:
        _fetch_movers(seen)    # lagging (already moved)
        _fetch_leading(seen)   # leading: upcoming earnings
    else:
        print("(info) no FMP_API_KEY — skipping FMP movers/earnings sources.")
    market, market_utc = _fetch_market_regime(prev)  # macro tape (throttled, FMP)
    smallcap = _fetch_smallcap_universe() if AV_API_KEY else {}  # small-cap map (discovery + enrichment)
    news_meta = _fetch_news(seen, prev, smallcap)  # news + small-cap-in-news discovery
    _write_candidates(seen, news_meta=news_meta, market=market, market_utc=market_utc)


def get_client() -> SchwabClient:
    auth = SchwabAuth(APP_KEY, APP_SECRET, CALLBACK)
    auth.refresh_token = REFRESH_TOKEN
    try:
        auth.refresh_access_token()
    except Exception as exc:  # noqa: BLE001
        resp = getattr(exc, "response", None)
        if resp is not None:
            print(f"Schwab token endpoint said: HTTP {resp.status_code} -> {resp.text}")
        raise
    return SchwabClient(APP_KEY, APP_SECRET, CALLBACK, auth=auth)


def _as_dict(o):
    if o is None:
        return {}
    if hasattr(o, "model_dump"):
        return o.model_dump()
    if isinstance(o, dict):
        return o
    return dict(o)


def load_orders() -> tuple[str | None, list[dict], dict]:
    if not os.path.exists(ORDERS_FILE):
        print(f"No {ORDERS_FILE} found.")
        return None, [], {}
    with open(ORDERS_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("generated_utc"), data.get("orders", []) or [], data.get("funnel") or {}


def is_fresh(generated_utc: str | None) -> bool:
    if not generated_utc:
        return True
    try:
        ts = datetime.fromisoformat(generated_utc.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    print(f"Signal generated {generated_utc} ({age_h:.1f}h ago; max {MAX_SIGNAL_AGE_HOURS}h)")
    return age_h <= MAX_SIGNAL_AGE_HOURS


def get_positions(client: SchwabClient) -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        for acct in client.get_accounts(include_positions=True):
            d = _as_dict(getattr(acct, "securities_account", None))
            for p in (d.get("positions") or []):
                pd = _as_dict(p)
                instr = pd.get("instrument") or {}
                sym = instr.get("symbol") if isinstance(instr, dict) else None
                qty = pd.get("longQuantity") or 0
                if sym and qty > 0:
                    out[sym] = {"qty": qty, "avg": pd.get("averagePrice") or 0}
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read positions: {exc}")
    return out


def write_holdings(positions: dict) -> None:
    """Write the account's REAL holdings to a file the brain trusts as ground truth."""
    data = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "holdings": [
            {"symbol": s, "quantity": p["qty"], "avg_price": p["avg"]}
            for s, p in sorted(positions.items())
        ],
    }
    try:
        os.makedirs(os.path.dirname(HOLDINGS_FILE), exist_ok=True)
        with open(HOLDINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        print(f"Wrote {HOLDINGS_FILE}: {len(data['holdings'])} holding(s)")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write holdings file: {exc}")


def _parse_dt(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except ValueError:
        return None


def get_blocked_buy_symbols(client: SchwabClient, account_hash: str) -> tuple[set[str], bool]:
    """Symbols we must NOT (re)buy this run: those with an OPEN buy order, OR a
    BUY order that was entered/filled within the last RECENT_BUY_COOLDOWN_MIN
    minutes. The cooldown closes the settlement-lag gap where a just-filled buy
    isn't in positions yet, which previously caused double-buys.
    Returns (symbols, ok); ok=False means we couldn't read orders (fail safe)."""
    blocked: set[str] = set()
    open_states = {"WORKING", "PENDING_ACTIVATION", "QUEUED", "ACCEPTED",
                   "AWAITING_PARENT_ORDER", "AWAITING_CONDITION", "NEW",
                   "PENDING_RECALL", "AWAITING_MANUAL_REVIEW", "AWAITING_STOP_CONDITION"}
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=RECENT_BUY_COOLDOWN_MIN)
        orders = client.get_orders(
            account_hash,
            from_entered_time=now - timedelta(days=5),
            to_entered_time=now + timedelta(minutes=5),
        )
        for o in orders:
            od = _as_dict(o)
            status = str(od.get("status", "")).upper()
            if status == "CANCELED" or status == "REJECTED" or status == "EXPIRED":
                continue
            entered = _parse_dt(od.get("enteredTime"))
            recent = entered is not None and entered >= cutoff
            for leg in (od.get("orderLegCollection") or []):
                ld = _as_dict(leg)
                instr = ld.get("instrument") or {}
                sym = instr.get("symbol") if isinstance(instr, dict) else None
                if not sym:
                    continue
                instruction = str(ld.get("instruction", "")).upper()
                # Block if a BUY is currently open, or any recent (open/filled) buy.
                if instruction.startswith("BUY") and (status in open_states or recent):
                    blocked.add(sym)
        return blocked, True
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read orders: {exc}")
        return blocked, False


def quote(client: SchwabClient, symbol: str) -> dict:
    try:
        q = client.get_quotes(symbol)
        d = _as_dict(q)
        found: dict[str, float] = {}

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, (int, float)):
                        found.setdefault(k.lower(), float(v))
                    walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)

        walk(d)
        return found
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) no quote for {symbol}: {exc}")
        return {}


def live_ask(q: dict) -> float | None:
    for k in ("askprice", "ask_price", "ask", "lastprice", "last_price", "mark"):
        if k in q and q[k]:
            return q[k]
    return None


def live_last(q: dict) -> float | None:
    for k in ("lastprice", "last_price", "mark", "bidprice", "bid_price"):
        if k in q and q[k]:
            return q[k]
    return None


def validate_pick(order: dict) -> tuple[bool, str]:
    if order.get("action") != "BUY":
        return False, "not a BUY"
    if order.get("instrument", "stock") != "stock":
        return False, "only stocks supported"
    qty = order.get("quantity") or 0
    limit = order.get("limit_price") or 0
    tp = order.get("take_profit") or 0
    sl = order.get("stop_loss") or 0
    if qty <= 0 or limit <= 0:
        return False, "bad quantity/limit_price"
    if limit < MIN_SHARE_PRICE:
        return False, f"under ${MIN_SHARE_PRICE:.0f} price floor (penny-stock guard)"
    if tp <= 0 or sl <= 0:
        return False, "missing take_profit/stop_loss"
    if tp < limit * (1 + MIN_TP_OVER_ENTRY) or sl > limit * (1 - MIN_STOP_UNDER_ENTRY):
        return False, "tp/stop not on correct sides of entry"
    return True, "ok"


def buy(client, acct, sym: str, qty: int, limit: float):
    if DRY_RUN:
        print(f"[{sym}] DRY-RUN: would BUY {qty} @ ${limit:.2f} = ${qty*limit:.2f}")
        return
    try:
        order = client.create_limit_order(
            symbol=sym, quantity=qty, limit_price=round(limit, 2),
            instruction=Instruction.buy, duration=Duration.day,
        )
        client.place_order(acct.hash_value, order)
        print(f"[{sym}] ✅ LIVE BUY {qty} @ ${limit:.2f} (marketable limit)")
    except Exception as exc:  # noqa: BLE001
        print(f"[{sym}] buy error: {exc}")


def sell(client, acct, sym: str, qty: int, limit: float, why: str):
    if DRY_RUN:
        print(f"[{sym}] DRY-RUN: would SELL {qty} @ ${limit:.2f} to close ({why})")
        return
    try:
        order = client.create_limit_order(
            symbol=sym, quantity=qty, limit_price=round(limit, 2),
            instruction=Instruction.sell, duration=Duration.day,
        )
        client.place_order(acct.hash_value, order)
        print(f"[{sym}] ✅ LIVE SELL {qty} @ ${limit:.2f} to close ({why})")
    except Exception as exc:  # noqa: BLE001
        print(f"[{sym}] sell error: {exc}")


def load_watchlist() -> list[dict]:
    """Brain-written names to auto-enter when a trigger fires between brain runs.
    The bot only READS this file (the brain owns it). Returns [] on any problem
    or if the file is stale (fail-safe — never act on an abandoned watchlist)."""
    if not os.path.exists(WATCHLIST_FILE):
        return []
    try:
        with open(WATCHLIST_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not read watchlist: {exc}")
        return []
    gen = _parse_dt(data.get("generated_utc"))
    if gen is not None:
        age_h = (datetime.now(timezone.utc) - gen).total_seconds() / 3600
        if age_h > MAX_WATCHLIST_AGE_HOURS:
            print(f"(info) watchlist is stale ({age_h:.0f}h > {MAX_WATCHLIST_AGE_HOURS}h) — ignoring.")
            return []
    return (data.get("watch") or [])[:MAX_WATCHLIST]


def watch_triggered(w: dict, q: dict) -> tuple[bool, str]:
    """Has this watch item's entry condition fired? breakout: live >= trigger_price;
    pullback: live <= trigger_price; date: today >= trigger_date."""
    trig = str(w.get("trigger", "")).lower()
    tp = w.get("trigger_price")
    last = live_last(q)
    if trig == "breakout":
        if last and tp and last >= tp:
            return True, f"broke ${tp} (last ${last})"
        return False, f"awaiting breakout > ${tp} (last ${last})"
    if trig == "pullback":
        if last and tp and last <= tp:
            return True, f"pulled back to ${tp} (last ${last})"
        return False, f"awaiting pullback <= ${tp} (last ${last})"
    if trig == "date":
        td = str(w.get("trigger_date") or w.get("good_until") or "")[:10]
        try:
            ok = datetime.now(timezone.utc).date() >= datetime.fromisoformat(td).date()
        except ValueError:
            return False, "bad trigger_date"
        return (ok, f"on/after {td}") if ok else (False, f"waiting for {td}")
    return False, f"unknown trigger '{trig}'"


def try_enter(client, acct, sym: str, want_qty, ref_limit: float,
              positions: dict, blocked: set, bought: set, q: dict | None = None) -> None:
    """Shared entry path for BOTH orders.json picks and watchlist triggers: dedupe,
    price off the LIVE ask, enforce the slippage backstop + $65 cap, then buy. The
    watchlist path passes the quote it already pulled (q) to avoid re-quoting."""
    if sym in positions:
        print(f"[{sym}] SKIP — already holding")
        return
    if sym in blocked:
        print(f"[{sym}] SKIP — open or recent buy order (no double-buy)")
        return
    if sym in bought:
        print(f"[{sym}] SKIP — already bought this run")
        return
    if q is None:
        q = quote(client, sym)
    ask = live_ask(q)
    if not ask:
        print(f"[{sym}] SKIP — no live quote")
        return
    if ask > ref_limit * (1 + MAX_SLIPPAGE):
        print(f"[{sym}] SKIP — ran away: live ask ${ask:.2f} > limit ${ref_limit:.2f} +{MAX_SLIPPAGE*100:.0f}%")
        return
    entry = round(ask * (1 + MARKETABLE_BUFFER), 2)  # marketable limit at the live ask
    qty = int(want_qty)
    while qty > 0 and qty * entry > MAX_DOLLARS_PER_TRADE:  # re-check cap on real price
        qty -= 1
    if qty <= 0:
        print(f"[{sym}] SKIP — 1 share at ${entry:.2f} exceeds ${MAX_DOLLARS_PER_TRADE:.0f} cap")
        return
    buy(client, acct, sym, qty, entry)
    bought.add(sym)


def main() -> int:
    mode = "DRY-RUN (no real orders)" if DRY_RUN else "LIVE (real orders!)"
    print(f"=== Executor | mode: {mode} ===")

    fetch_fmp_candidates()  # refresh the brain's structured candidate universe
    client = get_client()
    acct = client.get_account_numbers().accounts[0]
    positions = get_positions(client)
    write_holdings(positions)  # ground-truth holdings file for the brain
    blocked, orders_ok = get_blocked_buy_symbols(client, acct.hash_value)
    print(f"Held: {', '.join(positions) or '(none)'} | No-rebuy: "
          f"{', '.join(blocked) or '(none)'} | read_ok={orders_ok}")

    generated_utc, orders, funnel = load_orders()
    fresh = bool(orders) and is_fresh(generated_utc)
    if funnel:  # the brain's funnel tally (proof of how wide it scanned)
        print(f"Funnel this run: {funnel}")
    # Map each symbol -> its tp/stop from the latest picks (for exit management).
    levels = {o["symbol"]: o for o in orders if o.get("action") == "BUY"} if orders else {}
    brain_sells = {o.get("symbol") for o in orders if o.get("action") == "SELL"} if fresh else set()

    # Watchlist: brain-set names to auto-enter on a trigger between brain runs.
    # Merge their tp/stop into `levels` (orders.json wins) so a watchlist-triggered
    # fill still has exit protection before the brain next rewrites orders.json.
    watch = load_watchlist()
    for w in watch:
        wsym = w.get("symbol")
        if wsym and wsym not in levels:
            levels[wsym] = {"symbol": wsym, "action": "BUY",
                            "take_profit": w.get("take_profit"),
                            "stop_loss": w.get("stop_loss")}

    # ---- EXITS: manage held positions (sell-to-close on target/stop/brain) ----
    for sym, pos in positions.items():
        q = quote(client, sym)
        last = live_last(q)
        pick = levels.get(sym, {})
        tp = pick.get("take_profit")
        sl = pick.get("stop_loss")
        if sym in brain_sells:
            sell(client, acct, sym, int(pos["qty"]), last or pos["avg"], "brain SELL")
        elif last and tp and last >= tp:
            sell(client, acct, sym, int(pos["qty"]), last, f"hit target ${tp}")
        elif last and sl and last <= sl:
            sell(client, acct, sym, int(pos["qty"]), last, f"hit stop ${sl}")
        else:
            tptxt = f"${tp}" if tp else "?"
            sltxt = f"${sl}" if sl else "?"
            print(f"[{sym}] hold — last ${last} (target {tptxt} / stop {sltxt})")

    # ---- ENTRIES: priced off the LIVE ask. Two sources: watchlist triggers
    #      (independent of orders freshness) and fresh BUY picks from orders.json.
    if not orders_ok:
        print("SKIP all entries — could not read existing orders (fail-safe).")
        print("=== done ===")
        return 0
    bought: set[str] = set()  # symbols entered THIS run (prevents double-buys across both paths)

    # A) WATCHLIST triggers — enter when the brain-set condition fires.
    for w in watch:
        sym = w.get("symbol", "?")
        gu = str(w.get("good_until") or "")[:10]
        if gu:
            try:
                if datetime.now(timezone.utc).date() > datetime.fromisoformat(gu).date():
                    print(f"[{sym}] watch SKIP — expired (good_until {gu})")
                    continue
            except ValueError:
                pass
        pick = {"action": "BUY", "instrument": "stock", "quantity": w.get("quantity"),
                "limit_price": w.get("limit_price") or w.get("trigger_price"),
                "take_profit": w.get("take_profit"), "stop_loss": w.get("stop_loss")}
        ok, why = validate_pick(pick)
        if not ok:
            print(f"[{sym}] watch SKIP — {why}")
            continue
        q = quote(client, sym)
        fired, reason = watch_triggered(w, q)
        if not fired:
            print(f"[{sym}] watching — {reason}")
            continue
        print(f"[{sym}] watch TRIGGER — {reason}")
        try_enter(client, acct, sym, pick["quantity"], float(pick["limit_price"]),
                  positions, blocked, bought, q=q)

    # B) FRESH BUY picks from orders.json.
    if not fresh:
        print("No fresh BUY picks.")
    else:
        for order in orders:
            if order.get("action") != "BUY":
                continue
            sym = order.get("symbol", "?")
            ok, why = validate_pick(order)
            if not ok:
                print(f"[{sym}] SKIP — {why}")
                continue
            try_enter(client, acct, sym, order["quantity"], float(order["limit_price"]),
                      positions, blocked, bought)

    print("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
