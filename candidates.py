"""Market-data producer — builds the brain's structured top-of-funnel.

This is the DATA-GATHERING half of the system, split out of bot.py so it can run
on the BRAIN's schedule (gather -> think -> emit a trade plan) instead of on the
trader's. It has ZERO Schwab dependencies: pure stdlib urllib to FMP (movers +
earnings + market regime), Alpha Vantage (stock news), and Nasdaq's free public
screener (small-cap universe). Output is signals/candidates.json — write-only here;
only the brain reads it. The trader (bot.py) never touches this file.

It combines LAGGING movers (gainers/most-active/losers) with LEADING signals:
upcoming earnings (FMP) and stock news (Alpha Vantage). News tickers are cross-
referenced against a small-cap universe (Nasdaq's free public screener) to DISCOVER
small-caps that are in the news (not just annotate names we already had), so the
brain can position BEFORE a move. Each row is tagged with its reason(s). A top-level
`market` block gives the brain the macro tape to read first.

Run: `python candidates.py`  (no Schwab creds needed)
Optional env: FMP_API_KEY (movers + earnings + small-cap universe + market regime),
ALPHA_API_KEY (stock news + small-cap-in-news discovery). Missing keys just no-op
the corresponding sources; worst case the file is small or absent.
"""
from __future__ import annotations

import email.utils
import json
import os
import re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

# ===== KNOBS (data sources only; no money guardrails live here) =====
MIN_SHARE_PRICE       = 2.00    # hard floor: skip sub-$2 penny-stock pump/dump traps
CANDIDATES_FILE       = "signals/candidates.json"
FMP_BASE              = "https://financialmodelingprep.com/stable"
# --- leading-signal funnel (proactive: find names BEFORE they run) ---
EARNINGS_LOOKAHEAD_DAYS = 7     # enrich any candidate reporting within this window
EARNINGS_ADD_DAYS       = 7     # also ADD covered names reporting within this window
MAX_EARNINGS_ADD        = 80    # cap pre-earnings names added as fresh candidates
# --- trading halts / resumptions (Nasdaq Trader RSS; no key) ---
HALTS_URL             = "http://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
MAX_HALTS             = 60      # cap same-day halt/resume names added as candidates
# --- fresh SEC 8-K filings (SEC EDGAR; no key, descriptive User-Agent required) ---
SEC_8K_ATOM_URL       = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
                         "&type=8-K&company=&dateb=&owner=include&count=100&output=atom")
SEC_TICKERS_URL       = "https://www.sec.gov/files/company_tickers.json"
# SEC asks for a descriptive User-Agent with a contact email. Set SEC_CONTACT_EMAIL
# to your own address (env var / repo secret); the placeholder default works for low
# volume but identify yourself properly if you run this heavily.
SEC_CONTACT_EMAIL     = os.environ.get("SEC_CONTACT_EMAIL", "schwab-trader-bot@example.com").strip()
SEC_HEADERS           = {
    "User-Agent": f"schwab-trader/1.0 ({SEC_CONTACT_EMAIL})",
    "Accept": "application/atom+xml, application/xml, application/json, text/xml",
}
MAX_8K                = 80      # cap fresh same-day SEC 8-K names added as candidates
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
# ==============================

FMP_API_KEY   = os.environ.get("FMP_API_KEY", "").strip()
# Alpha Vantage stock-news key. Accept either name (the GitHub secret is ALPHA_API_KEY).
AV_API_KEY    = (os.environ.get("ALPHA_API_KEY") or os.environ.get("ALPHAVANTAGE_API_KEY", "")).strip()

# Cached SEC CIK -> ticker map (one fetch per process; the file is ~large but static).
_SEC_CIK_TICKERS: dict[int, str] | None = None


def _parse_dt(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except ValueError:
        return None


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


def _http_text(url: str, timeout: int = 20, retries: int = 2, headers: dict | None = None) -> str:
    """GET text/XML with the same transient-retry behavior as _http_json (used by the
    no-key Nasdaq-halts RSS and SEC EDGAR feeds, which return XML, not JSON)."""
    import time
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers=headers or {})
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raise  # permanent (404/403/...) — don't retry
            last_exc = exc  # 5xx: transient
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc  # network blip: transient
        if attempt < retries:
            time.sleep(0.5 * (2 ** attempt))
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
    sym = str(sym).strip().upper()  # normalize so the same ticker never splits into two rows
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


# ===== no-key LEADING feeds: trading halts (Nasdaq Trader) + fresh SEC 8-Ks (EDGAR) =====
# These need NO API key, so they run every time and are the reason the brain can drop its
# live "halts" / "8-K" web searches. Both are wrapped so a dead endpoint just no-ops.

def _xml_local(tag: str) -> str:
    """Strip any '{namespace}' prefix from an XML tag and lowercase it (RSS/Atom feeds
    namespace their elements, so we match on the local name only)."""
    return str(tag).rsplit("}", 1)[-1].lower()


def _xml_text(elem: ElementTree.Element, *names: str) -> str | None:
    """First non-empty text of any descendant whose local tag matches one of `names`."""
    wanted = {n.lower() for n in names}
    for child in elem.iter():
        if _xml_local(child.tag) in wanted and child.text:
            val = child.text.strip()
            if val:
                return val
    return None


def _xml_attr(elem: ElementTree.Element, name: str, attr: str) -> str | None:
    """Value of `attr` on the first descendant whose local tag matches `name`."""
    lname = name.lower()
    for child in elem.iter():
        if _xml_local(child.tag) == lname:
            val = child.attrib.get(attr)
            if val:
                return val.strip()
    return None


def _market_tz():
    """US market timezone for interpreting Nasdaq halt timestamps (they're ET, no zone)."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001 - Windows may lack zoneinfo data; fall back to UTC
        return timezone.utc


def _parse_halt_dt(date_val: str | None, time_val: str | None) -> datetime | None:
    """Parse a Nasdaq halt date+time (ET, several possible formats) -> UTC datetime."""
    if not date_val:
        return None
    raw_date = str(date_val).strip()
    raw_time = str(time_val or "").strip()
    if not raw_time or raw_time in {"-", "N/A"}:
        raw_time = "00:00:00"
    raw = f"{raw_date} {raw_time}"
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%m/%d/%y %H:%M:%S", "%m/%d/%y %H:%M",
                "%m/%d/%y %I:%M:%S %p", "%m/%d/%y %I:%M %p"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=_market_tz()).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _parse_feed_dt(val: str | None) -> datetime | None:
    """Parse an RSS/Atom timestamp (RFC822 via email.utils, ISO fallback) -> UTC."""
    if not val:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(str(val))
    except (TypeError, ValueError):
        parsed = _parse_dt(val)
    if not parsed:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_today_or_recent(dt: datetime | None, *, hours: int = 24) -> bool:
    """True if `dt` is today's UTC date OR within the last `hours` (freshness gate)."""
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    return dt.date() == now.date() or dt >= now - timedelta(hours=hours)


def _fetch_halts(seen: dict) -> None:
    """LEADING halt/resume funnel from the free Nasdaq Trader RSS — LULD halts often
    precede the biggest small-cap moves, so catching the RESUME is the edge. Keeps only
    today's/recent events, caps at MAX_HALTS, tags them `halt_resume`. A dead endpoint
    just no-ops (the brain simply won't see halts that run)."""
    try:
        xml = _http_text(HALTS_URL, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
        root = ElementTree.fromstring(xml)
        picked: list[dict] = []
        for item in root.iter():
            if _xml_local(item.tag) != "item":
                continue
            sym = (_xml_text(item, "IssueSymbol", "Symbol", "Ticker", "issue_symbol") or "").strip().upper()
            if not sym:
                continue
            halt_dt = _parse_halt_dt(
                _xml_text(item, "HaltDate", "TradeHaltDate", "halt_date"),
                _xml_text(item, "HaltTime", "TradeHaltTime", "halt_time"),
            )
            resume_dt = _parse_halt_dt(
                _xml_text(item, "ResumeDate", "ResumptionDate", "TradeResumeDate", "resume_date"),
                _xml_text(item, "ResumeTime", "ResumptionTime", "TradeResumeTime", "resume_time"),
            )
            event_dt = resume_dt or halt_dt or _parse_feed_dt(_xml_text(item, "pubDate", "updated"))
            if not _is_today_or_recent(event_dt, hours=24):
                continue
            picked.append({
                "sym": sym,
                "name": _xml_text(item, "IssueName", "CompanyName", "SecurityName", "Name"),
                "event_dt": event_dt,
                "resume_dt": resume_dt,
                "halt_dt": halt_dt,
                "reason": _xml_text(item, "ReasonCode", "HaltReason", "Reason", "ReasonCodeDescription"),
            })
        # Prefer names with a resumption set, then most recent event.
        picked.sort(key=lambda x: (x["resume_dt"] is not None, x["event_dt"] or datetime.min.replace(tzinfo=timezone.utc)),
                    reverse=True)
        added = 0
        for row in picked[:MAX_HALTS]:
            cat = {
                "halt_reason": row["reason"],
                "halt_time": row["halt_dt"].isoformat() if row["halt_dt"] else None,
                "resume_time": row["resume_dt"].isoformat() if row["resume_dt"] else None,
                "source": "nasdaqtrader",
                "published_utc": row["event_dt"].isoformat() if row["event_dt"] else None,
            }
            if _merge_candidate(seen, row["sym"], name=row["name"], lst="halts",
                                signal="halt_resume", catalyst=cat):
                added += 1
        print(f"(halts) +{added} halt/resume names")
    except Exception as exc:  # noqa: BLE001 - never let data fetch break the run
        print(f"(warn) trading halts fetch failed (skipped): {exc}")


def _sec_cik_tickers() -> dict[int, str]:
    """Fetch + cache SEC's CIK -> ticker map (company_tickers.json). One call per process."""
    global _SEC_CIK_TICKERS
    if _SEC_CIK_TICKERS is not None:
        return _SEC_CIK_TICKERS
    payload = _http_json(SEC_TICKERS_URL, timeout=25, headers=SEC_HEADERS)
    rows = payload.values() if isinstance(payload, dict) else payload
    out: dict[int, str] = {}
    for row in rows if isinstance(rows, list) or hasattr(rows, "__iter__") else []:
        if not isinstance(row, dict):
            continue
        try:
            cik = int(str(row.get("cik_str", "")).strip().lstrip("0") or "0")
        except ValueError:
            continue
        ticker = str(row.get("ticker", "")).strip().upper()
        if cik and ticker:
            out[cik] = ticker
    _SEC_CIK_TICKERS = out
    return out


def _entry_cik(entry: ElementTree.Element, title: str | None) -> int | None:
    """CIK for an EDGAR atom <entry> — from a <cik> element, else the '(0001234567)' in
    the title — normalized to an int (leading zeros stripped) to match the ticker map."""
    raw = _xml_text(entry, "cik", "cikNumber", "companyCik")
    if not raw and title:
        match = re.search(r"\((0*\d{1,10})\)", title)
        raw = match.group(1) if match else None
    if not raw:
        return None
    try:
        return int(str(raw).strip().lstrip("0") or "0")
    except ValueError:
        return None


def _entry_link(entry: ElementTree.Element) -> str | None:
    """Best filing URL for an EDGAR atom <entry> (link href, else id/link text)."""
    href = _xml_attr(entry, "link", "href")
    if href:
        return href
    return _xml_text(entry, "link", "id")


def _fetch_sec_8k(seen: dict) -> None:
    """LEADING funnel of FRESH SEC 8-K filings (material events: contracts, M&A, FDA,
    offerings) — the earliest catalyst, often before the stock moves. Maps each filing's
    CIK to a ticker, keeps only the last ~12h, dedupes by (ticker, url), caps at MAX_8K,
    tags `sec_8k`. SEC requires a descriptive User-Agent; failures no-op."""
    try:
        cik_map = _sec_cik_tickers()
        xml = _http_text(SEC_8K_ATOM_URL, timeout=25, headers=SEC_HEADERS)
        root = ElementTree.fromstring(xml)
        added = merged = 0
        filings_seen: set[tuple[str, str]] = set()
        for entry in root.iter():
            if _xml_local(entry.tag) != "entry":
                continue
            title = _xml_text(entry, "title")
            cik = _entry_cik(entry, title)
            sym = cik_map.get(cik) if cik else None
            if not sym:
                continue
            published = (_parse_dt(_xml_text(entry, "updated", "published")) or
                         _parse_feed_dt(_xml_text(entry, "updated", "published")))
            if not _is_today_or_recent(published, hours=12):
                continue
            url = _entry_link(entry) or _xml_text(entry, "id") or ""
            key = (sym, url)
            if key in filings_seen:
                continue
            filings_seen.add(key)
            cat = {
                "headline": title,
                "form": "8-K",
                "source": "sec_edgar",
                "published_utc": published.isoformat() if published else None,
                "url": url or None,
            }
            if _merge_candidate(seen, sym, name=sym, lst="sec", signal="sec_8k", catalyst=cat):
                added += 1
            else:
                merged += 1
            if added + merged >= MAX_8K:
                break
        print(f"(sec) 8-K: +{added} new, merged {merged}")
    except Exception as exc:  # noqa: BLE001 - never let SEC fetch break the run
        print(f"(warn) SEC 8-K fetch failed (skipped): {exc}")


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


def _slim_row(row: dict) -> dict:
    """Token-diet for the brain: drop fields that carry NO information — null/empty
    values and the redundant singular `signal` (the `signals` list already holds it).
    Lossless: every meaningful value (and the full `signals` list) is preserved, so
    the brain sees the identical candidate set and makes the identical decision."""
    return {k: v for k, v in row.items()
            if k != "signal" and v is not None and v != []}


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
        "candidates": [_slim_row(r) for r in sorted(seen.values(), key=lambda x: x["symbol"])],
    }
    try:
        os.makedirs(os.path.dirname(CANDIDATES_FILE), exist_ok=True)
        with open(CANDIDATES_FILE, "w", encoding="utf-8") as fh:
            # Compact separators (no pretty-print whitespace): ~46% fewer bytes/tokens
            # for the brain to read each run, with byte-for-byte the same parsed data.
            json.dump(data, fh, separators=(",", ":"))
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
            price, prev_close = row.get("price"), row.get("previousClose")  # note: not the `prev` param
            try:
                pct = (float(price) / float(prev_close) - 1.0) * 100.0 if price and prev_close else None
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
    the AV news call to stay under its 25/day free cap.
    The halts + SEC-8K feeds need NO key, so the prefetch runs even with no API keys set."""
    prev = _read_candidates()
    seen: dict[str, dict] = {}
    if FMP_API_KEY:
        _fetch_movers(seen)    # lagging (already moved)
        _fetch_leading(seen)   # leading: upcoming earnings
    else:
        print("(info) no FMP_API_KEY — skipping FMP movers/earnings sources.")
    _fetch_halts(seen)         # leading: same-day halt/resume feed (no key)
    _fetch_sec_8k(seen)        # leading: fresh material 8-K filings (no key)
    market, market_utc = _fetch_market_regime(prev)  # macro tape (throttled, FMP)
    smallcap = _fetch_smallcap_universe() if AV_API_KEY else {}  # small-cap map (discovery + enrichment)
    news_meta = _fetch_news(seen, prev, smallcap)  # news + small-cap-in-news discovery
    _write_candidates(seen, news_meta=news_meta, market=market, market_utc=market_utc)


def main() -> int:
    fetch_fmp_candidates()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
