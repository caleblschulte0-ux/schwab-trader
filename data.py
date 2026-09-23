"""Daily bar loading with a local cache. Keyless Yahoo source for backtests and as a
fallback for the live executor; Alpaca is the primary live source (see alpaca.py).
Pure stdlib."""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Bar = Tuple[str, float]  # (YYYY-MM-DD, adjusted close)

CACHE_DIR = os.environ.get("DATA_CACHE_DIR", "data_cache")   # full history, gitignored
SEED_DIR = "data_seed"                                          # trimmed copy, committed: outage fallback
SEED_ROWS = 520
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d&events=div"


def fetch_yahoo_daily(symbol: str, start_epoch: int = 820454400, timeout: int = 30) -> List[Bar]:
    """Adjusted daily closes from Yahoo's public chart endpoint (no key)."""
    url = YAHOO_URL.format(sym=symbol, p1=start_epoch, p2=int(time.time()) + 86400)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.load(r)
    res = j["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    out: List[Bar] = []
    for i, t in enumerate(ts):
        c = q["close"][i]
        if c is None:
            continue
        a = adj[i] if adj and adj[i] is not None else c
        out.append((time.strftime("%Y-%m-%d", time.gmtime(t)), float(a)))
    return out


def _cache_path(symbol: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}.csv")


def save_cache(symbol: str, bars: List[Bar]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(symbol), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "adjclose"])
        w.writerows(bars)


def load_cache(symbol: str, max_age_hours: Optional[float] = None) -> Optional[List[Bar]]:
    p = _cache_path(symbol)
    if not os.path.exists(p):
        return None
    if max_age_hours is not None and (time.time() - os.path.getmtime(p)) > max_age_hours * 3600:
        return None
    with open(p) as f:
        rd = csv.reader(f)
        next(rd, None)
        return [(row[0], float(row[1])) for row in rd if len(row) >= 2]


def load_seed(symbol: str) -> Optional[List[Bar]]:
    p = os.path.join(SEED_DIR, f"{symbol}.csv")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        rd = csv.reader(f)
        next(rd, None)
        return [(row[0], float(row[1])) for row in rd if len(row) >= 2]


def write_seed(symbols: List[str], rows: int = SEED_ROWS) -> int:
    """Copy the newest `rows` bars of each cached symbol into data_seed/ (committed)."""
    os.makedirs(SEED_DIR, exist_ok=True)
    n = 0
    for s in symbols:
        bars = load_cache(s, None)
        if not bars:
            continue
        with open(os.path.join(SEED_DIR, f"{s}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "adjclose"])
            w.writerows(bars[-rows:])
        n += 1
    return n


def load_history(symbols: List[str], refresh: bool = False, max_age_hours: Optional[float] = 12) -> Dict[str, List[Bar]]:
    """Yahoo history per symbol: local cache -> Yahoo -> stale cache -> committed seed.
    Symbols that fail everywhere are skipped (and reported)."""
    out: Dict[str, List[Bar]] = {}
    for s in symbols:
        bars = None if refresh else load_cache(s, max_age_hours)
        if bars is None:
            try:
                bars = fetch_yahoo_daily(s)
                save_cache(s, bars)
                time.sleep(0.25)
            except Exception as exc:  # noqa: BLE001
                fallback = load_cache(s, None) or load_seed(s)
                if fallback:
                    print(f"(data) {s}: fetch failed ({exc}); using fallback data ending {fallback[-1][0]}")
                    bars = fallback
                else:
                    print(f"(data) {s}: fetch failed ({exc}); skipping")
                    continue
        out[s] = bars
    return out


if __name__ == "__main__":
    import sys
    from strategy import DEFENSIVE, LEVERAGED, UNIVERSE
    syms = sorted(set(UNIVERSE) | set(DEFENSIVE) | set(LEVERAGED.values()))
    if "--seed" in sys.argv:
        load_history(syms, refresh=True, max_age_hours=None)
        print(f"(data) wrote seed for {write_seed(syms)} symbols -> {SEED_DIR}/")
    else:
        h = load_history(syms, refresh="--refresh" in sys.argv, max_age_hours=None)
        for s in syms:
            b = h.get(s)
            print(f"{s:5} {len(b) if b else 0:5} bars  {b[-1][0] if b else '-'}")
