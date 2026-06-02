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
It combines LAGGING movers (gainers/most-active/losers) with LEADING signals
(analyst upgrades, raised price targets, upcoming earnings) so the brain can
position BEFORE a move, not just chase it. Each row is tagged with its reason(s).
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
Optional: SCHWAB_CALLBACK_URL, DRY_RUN, FMP_API_KEY (market-mover candidates)
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
EARNINGS_ADD_DAYS       = 3     # also ADD covered names reporting within this window
MAX_EARNINGS_ADD        = 50    # cap pre-earnings names added as fresh candidates
ANALYST_LIMIT           = 100   # newest N analyst-action rows to scan per feed
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


def _fmp_get(endpoint: str, params: str = "") -> list:
    """GET one FMP /stable endpoint -> list of rows. Never raises (returns [])."""
    import urllib.request
    sep = "&" if params else ""
    url = f"{FMP_BASE}/{endpoint}?{params}{sep}apikey={FMP_API_KEY}"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def _merge_candidate(seen: dict, sym: str, *, name=None, price=None, pct=None,
                     exch=None, lst=None, signal=None, catalyst=None) -> bool:
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
    if signal and signal not in row.get("signals", []):
        row.setdefault("signals", []).append(signal)
    if catalyst:
        row.setdefault("catalyst", {}).update(catalyst)
    return False


# Higher score = more bullish. Used to tell an UPGRADE from a downgrade so we
# never inject a freshly-DOWNGRADED (bearish) name into a BUY funnel.
_GRADE_SCORE = {
    "strong sell": 0, "sell": 1, "underperform": 1, "underweight": 1, "reduce": 1,
    "negative": 1, "hold": 2, "neutral": 2, "market perform": 2, "equal-weight": 2,
    "equalweight": 2, "sector perform": 2, "in-line": 2, "peer perform": 2,
    "accumulate": 3, "add": 3, "overweight": 3, "outperform": 4, "buy": 4,
    "positive": 4, "market outperform": 4, "sector outperform": 4, "strong buy": 5,
}


def _grade_score(grade) -> int | None:
    if not grade:
        return None
    return _GRADE_SCORE.get(str(grade).strip().lower())


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
                lst=label, signal="mover") for row in rows)
            print(f"(fmp) {label}: +{n} new")
        except Exception as exc:  # noqa: BLE001 - never let data fetch break the run
            print(f"(warn) FMP {label} fetch failed: {exc}")


def _fetch_leading(seen: dict) -> None:
    """LEADING funnel (the proactive upgrade): names with a FRESH or PENDING
    catalyst — analyst UPGRADES, raised PRICE TARGETS, and UPCOMING EARNINGS —
    so the brain can position BEFORE the move, not just chase it after.
    Each source is isolated in try/except: a failed/paid endpoint just no-ops."""
    # 1) Analyst UPGRADES (bullish grade changes only).
    try:
        n = 0
        for row in _fmp_get("grade-latest-news", f"page=0&limit={ANALYST_LIMIT}"):
            sym = row.get("symbol")
            new_s = _grade_score(row.get("newGrade"))
            prev_s = _grade_score(row.get("previousGrade"))
            action = str(row.get("action", "")).strip().lower()
            is_up = (action in {"upgrade", "initialise", "initialize", "initiate"}
                     or (new_s is not None and prev_s is not None and new_s > prev_s)
                     or (prev_s is None and new_s is not None and new_s >= 4))
            if not is_up:
                continue  # skip downgrades / holds / unknowns — buy funnel only
            _merge_candidate(seen, sym, signal="upgrade", lst="analyst", catalyst={
                "analyst_firm": row.get("gradingCompany"),
                "from_grade": row.get("previousGrade"), "to_grade": row.get("newGrade")})
            n += 1
        print(f"(fmp) upgrades: +{n}")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) FMP grade-latest-news failed (skipped): {exc}")

    # 2) Raised PRICE TARGETS (target meaningfully above price when posted).
    try:
        n = 0
        for row in _fmp_get("price-target-latest-news", f"page=0&limit={ANALYST_LIMIT}"):
            sym = row.get("symbol")
            pt = row.get("priceTarget") or row.get("adjPriceTarget")
            when = row.get("priceWhenPosted")
            if not (pt and when and pt > when * 1.05):  # need real implied upside
                continue
            _merge_candidate(seen, sym, signal="pt_raise", lst="analyst", catalyst={
                "analyst_firm": row.get("analystCompany") or row.get("newsPublisher"),
                "price_target": pt})
            n += 1
        print(f"(fmp) price-target raises: +{n}")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) FMP price-target-latest-news failed (skipped): {exc}")

    # 3) UPCOMING EARNINGS — the highest-value leading signal. Two uses:
    #    (a) ENRICH any existing candidate that reports soon (a mover reporting
    #        tomorrow is high-priority); (b) ADD a capped set of covered names
    #        reporting in the next few days that aren't on any list yet.
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
            if sym in seen:
                _merge_candidate(seen, sym, signal="earnings_soon",
                                 catalyst={"earnings_date": raw})
                enriched += 1
            elif (added < MAX_EARNINGS_ADD and edate <= today + timedelta(days=EARNINGS_ADD_DAYS)
                  and row.get("epsEstimated") is not None):  # epsEstimated => covered/liquid
                _merge_candidate(seen, sym, name=sym, lst="calendar",
                                 signal="earnings_soon", catalyst={"earnings_date": raw})
                added += 1
        print(f"(fmp) earnings: enriched {enriched}, added {added} upcoming")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) FMP earnings-calendar failed (skipped): {exc}")


def _write_candidates(seen: dict) -> None:
    counts: dict[str, int] = {}
    for row in seen.values():
        for s in (row.get("signals") or ([row["signal"]] if row.get("signal") else [])):
            counts[s] = counts.get(s, 0) + 1
    data = {
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(seen),
        "signal_counts": counts,
        "candidates": sorted(seen.values(), key=lambda x: x["symbol"]),
    }
    try:
        os.makedirs(os.path.dirname(CANDIDATES_FILE), exist_ok=True)
        with open(CANDIDATES_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        print(f"Wrote {CANDIDATES_FILE}: {len(seen)} candidates {counts}")
    except Exception as exc:  # noqa: BLE001
        print(f"(warn) could not write candidates file: {exc}")


def fetch_fmp_candidates() -> None:
    """Build the brain's structured top-of-funnel and write signals/candidates.json.
    Combines a LAGGING list (today's movers) with LEADING signals (analyst upgrades,
    raised price targets, upcoming earnings) so the brain can act BEFORE the move.
    ~6 FMP calls/run (free-tier safe, ~216/day < 250). No-ops without a key; any one
    source failing is non-fatal — worst case the file is just today's movers."""
    if not FMP_API_KEY:
        print("(info) no FMP_API_KEY set — skipping candidate prefetch.")
        return
    seen: dict[str, dict] = {}
    _fetch_movers(seen)    # lagging (already moved)
    _fetch_leading(seen)   # leading (about to / catalyst pending)
    _write_candidates(seen)


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


def load_orders() -> tuple[str | None, list[dict]]:
    if not os.path.exists(ORDERS_FILE):
        print(f"No {ORDERS_FILE} found.")
        return None, []
    with open(ORDERS_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("generated_utc"), data.get("orders", []) or []


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
              positions: dict, blocked: set, bought: set) -> None:
    """Shared entry path for BOTH orders.json picks and watchlist triggers: dedupe,
    price off the LIVE ask, enforce the slippage backstop + $65 cap, then buy."""
    if sym in positions:
        print(f"[{sym}] SKIP — already holding")
        return
    if sym in blocked:
        print(f"[{sym}] SKIP — open or recent buy order (no double-buy)")
        return
    if sym in bought:
        print(f"[{sym}] SKIP — already bought this run")
        return
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

    generated_utc, orders = load_orders()
    fresh = bool(orders) and is_fresh(generated_utc)
    # Show the brain's funnel tally if present (proof of how wide it scanned).
    try:
        with open(ORDERS_FILE, encoding="utf-8") as _fh:
            _funnel = json.load(_fh).get("funnel")
        if _funnel:
            print(f"Funnel this run: {_funnel}")
    except Exception:
        pass
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
        fired, reason = watch_triggered(w, quote(client, sym))
        if not fired:
            print(f"[{sym}] watching — {reason}")
            continue
        print(f"[{sym}] watch TRIGGER — {reason}")
        try_enter(client, acct, sym, pick["quantity"], float(pick["limit_price"]),
                  positions, blocked, bought)

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
