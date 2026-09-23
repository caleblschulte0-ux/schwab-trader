"""Minimal Alpaca REST client (trading + market data). Pure stdlib, no SDK.

Why Alpaca: static API key/secret (no OAuth refresh token that dies every 7 days
like Schwab's), a real paper-trading account that mirrors live, commission-free
ETFs, fractional shares, and a free daily-bar data feed. Paper and live use the
same code path -- only the base URL changes.

    ALPACA_API_KEY / ALPACA_SECRET_KEY  -> from https://app.alpaca.markets (Paper or Live keys)
    paper=True  -> https://paper-api.alpaca.markets
    paper=False -> https://api.alpaca.markets
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

TRADING_PAPER = "https://paper-api.alpaca.markets"
TRADING_LIVE = "https://api.alpaca.markets"
DATA = "https://data.alpaca.markets"


class AlpacaError(RuntimeError):
    def __init__(self, status: int, body: str, url: str):
        super().__init__(f"HTTP {status} from {url}: {body[:300]}")
        self.status = status
        self.body = body
        self.url = url


class Alpaca:
    def __init__(self, key: str, secret: str, paper: bool = True, timeout: int = 30):
        if not key or not secret:
            raise ValueError("Alpaca key/secret required")
        self.key = key
        self.secret = secret
        self.paper = paper
        self.base = TRADING_PAPER if paper else TRADING_LIVE
        self.timeout = timeout

    # ------------------------------------------------------------------ http
    def _req(self, method: str, url: str, params: Optional[dict] = None, body: Optional[dict] = None,
             retries: int = 3) -> Any:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret,
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        last: Optional[Exception] = None
        for attempt in range(retries):
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read().decode() or "null"
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                body_txt = e.read().decode(errors="replace")
                # 429 rate limit / 5xx -> back off and retry; everything else is final
                if e.code == 429 or e.code >= 500:
                    last = AlpacaError(e.code, body_txt, url)
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise AlpacaError(e.code, body_txt, url) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
        assert last is not None
        raise last

    def _t(self, method: str, path: str, **kw) -> Any:
        return self._req(method, self.base + path, **kw)

    def _d(self, method: str, path: str, **kw) -> Any:
        return self._req(method, DATA + path, **kw)

    # --------------------------------------------------------------- account
    def account(self) -> dict:
        return self._t("GET", "/v2/account")

    def clock(self) -> dict:
        """{'timestamp','is_open','next_open','next_close'}"""
        return self._t("GET", "/v2/clock")

    def calendar(self, start: str, end: str) -> List[dict]:
        return self._t("GET", "/v2/calendar", params={"start": start, "end": end})

    def positions(self) -> List[dict]:
        return self._t("GET", "/v2/positions") or []

    def close_position(self, symbol: str) -> dict:
        return self._t("DELETE", f"/v2/positions/{symbol}")

    def close_all_positions(self, cancel_orders: bool = True) -> Any:
        return self._t("DELETE", "/v2/positions", params={"cancel_orders": "true" if cancel_orders else "false"})

    def open_orders(self) -> List[dict]:
        return self._t("GET", "/v2/orders", params={"status": "open", "limit": 500}) or []

    def cancel_order(self, order_id: str) -> Any:
        return self._t("DELETE", f"/v2/orders/{order_id}")

    def cancel_all_orders(self) -> Any:
        return self._t("DELETE", "/v2/orders")

    def get_order(self, order_id: str) -> dict:
        return self._t("GET", f"/v2/orders/{order_id}")

    def submit_order(self, symbol: str, side: str, notional: Optional[float] = None, qty: Optional[float] = None,
                     order_type: str = "market", tif: str = "day", client_order_id: Optional[str] = None) -> dict:
        if (notional is None) == (qty is None):
            raise ValueError("pass exactly one of notional / qty")
        body: Dict[str, Any] = {"symbol": symbol, "side": side, "type": order_type, "time_in_force": tif}
        if notional is not None:
            body["notional"] = f"{notional:.2f}"
        else:
            body["qty"] = f"{qty:g}"
        if client_order_id:
            body["client_order_id"] = client_order_id[:48]
        return self._t("POST", "/v2/orders", body=body)

    def wait_for_fill(self, order_id: str, timeout_s: float = 45.0, poll_s: float = 1.5) -> dict:
        """Poll until the order leaves the open states (filled/canceled/rejected...)."""
        deadline = time.time() + timeout_s
        o = self.get_order(order_id)
        while o.get("status") in ("new", "accepted", "pending_new", "accepted_for_bidding", "partially_filled") and time.time() < deadline:
            time.sleep(poll_s)
            o = self.get_order(order_id)
        return o

    def asset(self, symbol: str) -> dict:
        return self._t("GET", f"/v2/assets/{symbol}")

    def portfolio_history(self, period: str = "1A", timeframe: str = "1D", extended_hours: bool = False) -> dict:
        return self._t("GET", "/v2/account/portfolio/history",
                       params={"period": period, "timeframe": timeframe, "extended_hours": "true" if extended_hours else "false"})

    def fills(self, after: Optional[str] = None, until: Optional[str] = None) -> List[dict]:
        """All FILL activities (paged). after/until are ISO dates/timestamps."""
        out: List[dict] = []
        page_token: Optional[str] = None
        while True:
            params = {"after": after, "until": until, "page_size": 100, "direction": "asc", "page_token": page_token}
            page = self._t("GET", "/v2/account/activities/FILL", params=params) or []
            out.extend(page)
            if len(page) < 100:
                break
            page_token = page[-1].get("id")
            if not page_token:
                break
        return out

    def cash_flows(self, after: Optional[str] = None) -> float:
        """Net external cash movement (deposits - withdrawals, journals, ACATS) since `after`.
        Used to keep the drawdown high-water mark honest when money moves in or out."""
        total = 0.0
        page_token: Optional[str] = None
        while True:
            params = {"activity_types": "CSD,CSW,JNLC,ACATC,ACATS", "after": after, "page_size": 100,
                      "direction": "asc", "page_token": page_token}
            page = self._t("GET", "/v2/account/activities", params=params) or []
            for act in page:
                try:
                    total += float(act.get("net_amount") or 0.0)
                except (TypeError, ValueError):
                    pass
            if len(page) < 100:
                break
            page_token = page[-1].get("id")
            if not page_token:
                break
        return total

    # ----------------------------------------------------------------- data
    def daily_bars(self, symbols: Iterable[str], start: str, end: Optional[str] = None,
                   adjustment: str = "all", feed: Optional[str] = None) -> Dict[str, List[Tuple[str, float]]]:
        """symbol -> [(YYYY-MM-DD, close)] using the multi-symbol bars endpoint.
        adjustment='all' = split+dividend adjusted (matches the backtest's adjusted closes).
        Free plans: 'sip' works for data older than 15 minutes; on a 4xx we fall back to 'iex'."""
        syms = sorted(set(symbols))
        out: Dict[str, List[Tuple[str, float]]] = {s: [] for s in syms}
        feeds = [feed] if feed else ["sip", "iex"]
        last_err: Optional[Exception] = None
        for fd in feeds:
            try:
                out = {s: [] for s in syms}
                for i in range(0, len(syms), 50):
                    chunk = syms[i:i + 50]
                    token: Optional[str] = None
                    while True:
                        params = {"symbols": ",".join(chunk), "timeframe": "1Day", "start": start, "end": end,
                                  "limit": 10000, "adjustment": adjustment, "feed": fd, "sort": "asc", "page_token": token}
                        page = self._d("GET", "/v2/stocks/bars", params=params)
                        for s, bars in (page.get("bars") or {}).items():
                            for b in bars:
                                out[s].append((str(b["t"])[:10], float(b["c"])))
                        token = page.get("next_page_token")
                        if not token:
                            break
                return out
            except AlpacaError as e:
                last_err = e
                if e.status in (400, 402, 403, 422):
                    continue
                raise
        assert last_err is not None
        raise last_err

    def latest_prices(self, symbols: Iterable[str], feed: str = "iex") -> Dict[str, float]:
        """Best-available current price per symbol from the snapshots endpoint."""
        syms = sorted(set(symbols))
        out: Dict[str, float] = {}
        for i in range(0, len(syms), 100):
            chunk = syms[i:i + 100]
            snap = self._d("GET", "/v2/stocks/snapshots", params={"symbols": ",".join(chunk), "feed": feed}) or {}
            for s, v in snap.items():
                if not isinstance(v, dict):
                    continue
                p = None
                for key in ("latestTrade", "minuteBar", "dailyBar", "prevDailyBar"):
                    node = v.get(key) or {}
                    p = node.get("p") if key == "latestTrade" else node.get("c")
                    if p:
                        break
                if p:
                    out[s] = float(p)
        return out
