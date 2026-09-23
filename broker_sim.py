"""Built-in simulator broker: the same interface as alpaca.Alpaca, backed by a JSON
file in the repo and keyless Yahoo prices. Lets the whole system run, trade, and
build a track record BEFORE any brokerage keys exist. Fills at the current price
with a conservative 5 bps of slippage (same as the backtest)."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import data as datamod
from strategy import DEFENSIVE, LEVERAGED, UNIVERSE

ET = ZoneInfo("America/New_York")
SIM_FILE = os.path.join("signals", "sim_account.json")
SLIPPAGE = 0.0005


class SimBroker:
    mode = "sim"
    paper = True

    def __init__(self, path: str = SIM_FILE, start_cash: float = 1000.0,
                 history: Optional[Dict[str, List[Tuple[str, float]]]] = None, now: Optional[datetime] = None):
        self.path = path
        self._history = history
        self._now = now
        self.book = self._load() or {
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "start_cash": start_cash, "cash": start_cash, "positions": {}, "fills": [], "equity_curve": [], "n": 0,
        }

    # ------------------------------------------------------------ persistence
    def _load(self) -> Optional[dict]:
        try:
            with open(self.path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.book, f, indent=2, sort_keys=True)
            f.write("\n")

    # ------------------------------------------------------------ time
    def now_et(self) -> datetime:
        return (self._now or datetime.now(timezone.utc)).astimezone(ET)

    @staticmethod
    def _fmt(d: datetime) -> str:
        return d.isoformat(timespec="seconds")

    def clock(self) -> dict:
        now = self.now_et()
        open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
        close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
        is_open = now.weekday() < 5 and open_t <= now < close_t
        if is_open:
            next_close = close_t
            next_open = open_t + timedelta(days=1)
        else:
            d = now
            if now >= close_t or now.weekday() >= 5:
                d = now + timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)
            next_open = d.replace(hour=9, minute=30, second=0, microsecond=0)
            next_close = d.replace(hour=16, minute=0, second=0, microsecond=0)
        return {"timestamp": self._fmt(now), "is_open": is_open,
                "next_open": self._fmt(next_open), "next_close": self._fmt(next_close)}

    def calendar(self, start: str, end: str) -> List[dict]:
        d = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
        out = []
        while d <= e:
            if d.weekday() < 5:
                out.append({"date": d.strftime("%Y-%m-%d"), "open": "09:30", "close": "16:00"})
            d += timedelta(days=1)
        return out

    # ------------------------------------------------------------ prices
    def _hist(self) -> Dict[str, List[Tuple[str, float]]]:
        if self._history is None:
            syms = sorted(set(UNIVERSE) | set(DEFENSIVE) | set(LEVERAGED.values()) | set(self.book["positions"]))
            self._history = datamod.load_history(syms, refresh=True, max_age_hours=None)
        return self._history

    def price(self, symbol: str) -> float:
        h = self._hist().get(symbol) or []
        return h[-1][1] if h else 0.0

    def daily_bars(self, symbols: Iterable[str], start: str, end: Optional[str] = None,
                   adjustment: str = "all", feed: Optional[str] = None) -> Dict[str, List[Tuple[str, float]]]:
        h = self._hist()
        return {s: [(d, c) for d, c in h.get(s, []) if d >= start and (end is None or d <= end)] for s in symbols}

    def latest_prices(self, symbols: Iterable[str], feed: str = "iex") -> Dict[str, float]:
        return {s: self.price(s) for s in symbols if self.price(s) > 0}

    # ------------------------------------------------------------ account
    def _equity(self) -> float:
        return self.book["cash"] + sum(p["qty"] * self.price(s) for s, p in self.book["positions"].items())

    def account(self) -> dict:
        eq = self._equity()
        return {"equity": f"{eq:.2f}", "cash": f"{self.book['cash']:.2f}", "buying_power": f"{self.book['cash']:.2f}",
                "trading_blocked": False, "account_blocked": False, "multiplier": "1"}

    def positions(self) -> List[dict]:
        out = []
        for s, p in sorted(self.book["positions"].items()):
            px = self.price(s)
            mv = p["qty"] * px
            cost = p["qty"] * p["avg_entry"]
            out.append({"symbol": s, "qty": f"{p['qty']:.6f}", "avg_entry_price": f"{p['avg_entry']:.4f}",
                        "current_price": f"{px:.4f}", "market_value": f"{mv:.2f}",
                        "unrealized_pl": f"{mv - cost:.2f}", "unrealized_plpc": f"{(mv / cost - 1) if cost else 0:.6f}"})
        return out

    def asset(self, symbol: str) -> dict:
        return {"symbol": symbol, "tradable": self.price(symbol) > 0, "fractionable": True}

    # ------------------------------------------------------------ orders
    def _fill(self, symbol: str, side: str, qty: float) -> dict:
        px = self.price(symbol)
        if px <= 0 or qty <= 0:
            raise RuntimeError(f"sim: cannot fill {side} {symbol}")
        fill_px = px * (1 + SLIPPAGE) if side == "buy" else px * (1 - SLIPPAGE)
        pos = self.book["positions"].get(symbol, {"qty": 0.0, "avg_entry": 0.0})
        if side == "buy":
            cost = qty * fill_px
            if cost > self.book["cash"] + 1e-6:
                raise RuntimeError(f"sim: insufficient cash for {symbol}: {cost:.2f} > {self.book['cash']:.2f}")
            new_qty = pos["qty"] + qty
            pos["avg_entry"] = (pos["qty"] * pos["avg_entry"] + cost) / new_qty
            pos["qty"] = new_qty
            self.book["cash"] -= cost
            self.book["positions"][symbol] = pos
        else:
            qty = min(qty, pos["qty"])
            pos["qty"] -= qty
            self.book["cash"] += qty * fill_px
            if pos["qty"] <= 1e-9:
                self.book["positions"].pop(symbol, None)
            else:
                self.book["positions"][symbol] = pos
        self.book["n"] += 1
        oid = f"sim-{self.book['n']}"
        ts = self.now_et().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.book["fills"].append({"id": oid, "symbol": symbol, "side": side, "qty": f"{qty:.6f}",
                                   "price": f"{fill_px:.4f}", "transaction_time": ts})
        self.save()
        return {"id": oid, "status": "filled", "symbol": symbol, "side": side,
                "filled_qty": f"{qty:.6f}", "filled_avg_price": f"{fill_px:.4f}"}

    def submit_order(self, symbol: str, side: str, notional: Optional[float] = None, qty: Optional[float] = None,
                     order_type: str = "market", tif: str = "day", client_order_id: Optional[str] = None) -> dict:
        if qty is None:
            px = self.price(symbol)
            qty = (notional or 0.0) / (px * (1 + SLIPPAGE)) if px > 0 else 0.0
        return self._fill(symbol, side, float(qty))

    def close_position(self, symbol: str) -> dict:
        pos = self.book["positions"].get(symbol)
        if not pos:
            return {"id": "none", "status": "canceled", "symbol": symbol}
        return self._fill(symbol, "sell", pos["qty"])

    def close_all_positions(self, cancel_orders: bool = True):
        return [self.close_position(s) for s in list(self.book["positions"])]

    def wait_for_fill(self, order_id: str, timeout_s: float = 45.0, poll_s: float = 1.5) -> dict:
        return self.get_order(order_id)

    def get_order(self, order_id: str) -> dict:
        for f in self.book["fills"]:
            if f["id"] == order_id:
                return {"id": order_id, "status": "filled", "symbol": f["symbol"], "side": f["side"],
                        "filled_qty": f["qty"], "filled_avg_price": f["price"]}
        return {"id": order_id, "status": "unknown"}

    def cash_flows(self, after: Optional[str] = None) -> float:
        return 0.0

    def open_orders(self) -> List[dict]:
        return []

    def cancel_order(self, order_id: str):
        return None

    def cancel_all_orders(self):
        return []

    # ------------------------------------------------------------ history / reporting
    def snapshot(self) -> None:
        """Record today's equity (one point per day) and persist."""
        today = self.now_et().strftime("%Y-%m-%d")
        eq = round(self._equity(), 2)
        curve = [pt for pt in self.book["equity_curve"] if pt[0] != today]
        curve.append([today, eq])
        self.book["equity_curve"] = sorted(curve)
        self.save()

    def portfolio_history(self, period: str = "1A", timeframe: str = "1D", extended_hours: bool = False) -> dict:
        ts, eq = [], []
        for d, e in self.book["equity_curve"]:
            ts.append(int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()))
            eq.append(e)
        return {"timestamp": ts, "equity": eq, "timeframe": timeframe, "base_value": self.book["start_cash"]}

    def fills(self, after: Optional[str] = None, until: Optional[str] = None) -> List[dict]:
        out = self.book["fills"]
        if after:
            out = [f for f in out if f["transaction_time"] >= after]
        if until:
            out = [f for f in out if f["transaction_time"] <= until]
        return list(out)
