"""End-to-end test of the executor against a fake in-memory Alpaca.
Exercises: window guard, first-day decision, order planning (sells before buys,
cash cap), idempotent same-day re-run, kill switch. No network."""
import json
import math
import os
import random
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot
from strategy import UNIVERSE


def synth(seed, n=400, drift=0.0005, vol=0.01, start=100.0):
    rnd = random.Random(seed)
    c = [start]
    for _ in range(n - 1):
        c.append(c[-1] * math.exp(drift + vol * rnd.gauss(0, 1)))
    return c


class FakeAlpaca:
    """Enough of alpaca.Alpaca for bot.main(): instant fills at the live price."""
    instances = []
    book = {"cash": 1000.0, "pos": {}}   # shared across instances, reset per test

    @property
    def cash(self):
        return FakeAlpaca.book["cash"]

    @cash.setter
    def cash(self, v):
        FakeAlpaca.book["cash"] = v

    @property
    def pos(self):
        return FakeAlpaca.book["pos"]

    @pos.setter
    def pos(self, v):
        FakeAlpaca.book["pos"] = v

    def __init__(self, key, secret, paper=True, timeout=30):
        self.paper = paper
        self.orders = {}
        self.n = 0
        self.is_open = True
        self.now = "2026-09-22T15:40:00.123456789-04:00"
        self.next_close = "2026-09-22T16:00:00-04:00"
        rnd = random.Random(42)
        self.hist = {s: synth(rnd.randint(0, 9999), 400, rnd.uniform(-0.0005, 0.0015)) for s in UNIVERSE}
        self.hist["BIL"] = synth(1, 400, 0.0001, 0.0002)
        self.px = {s: v[-1] for s, v in self.hist.items()}
        self.calls = []
        FakeAlpaca.instances.append(self)

    # account
    def equity(self):
        return self.cash + sum(q * self.px[s] for s, q in self.pos.items())

    def account(self):
        return {"equity": str(self.equity()), "cash": str(self.cash), "buying_power": str(self.cash),
                "trading_blocked": False, "account_blocked": False}

    def clock(self):
        return {"timestamp": self.now, "is_open": self.is_open, "next_open": "2026-09-23T09:30:00-04:00",
                "next_close": self.next_close}

    def positions(self):
        return [{"symbol": s, "qty": str(q), "avg_entry_price": "1", "current_price": str(self.px[s]),
                 "market_value": str(q * self.px[s]), "unrealized_pl": "0", "unrealized_plpc": "0"}
                for s, q in self.pos.items() if q > 1e-9]

    def close_position(self, symbol):
        q = self.pos.pop(symbol, 0.0)
        self.cash += q * self.px[symbol]
        self.calls.append(("close", symbol, q * self.px[symbol]))
        return self._order(symbol, "sell", q)

    def _order(self, symbol, side, qty):
        self.n += 1
        oid = f"o{self.n}"
        self.orders[oid] = {"id": oid, "status": "filled", "filled_qty": str(qty), "filled_avg_price": str(self.px[symbol]), "symbol": symbol}
        return self.orders[oid]

    def submit_order(self, symbol, side, notional=None, qty=None, order_type="market", tif="day", client_order_id=None):
        q = qty if qty is not None else notional / self.px[symbol]
        if side == "buy":
            cost = q * self.px[symbol]
            assert cost <= self.cash + 1e-6, f"overspent: {cost} > {self.cash}"
            self.cash -= cost
            self.pos[symbol] = self.pos.get(symbol, 0.0) + q
        else:
            self.pos[symbol] = self.pos.get(symbol, 0.0) - q
            self.cash += q * self.px[symbol]
        self.calls.append((side, symbol, q * self.px[symbol]))
        return self._order(symbol, side, q)

    def wait_for_fill(self, oid, timeout_s=45.0, poll_s=1.5):
        return self.orders[oid]

    def get_order(self, oid):
        return self.orders[oid]

    def asset(self, symbol):
        return {"symbol": symbol, "tradable": True, "fractionable": True}

    # data
    def daily_bars(self, symbols, start, end=None, adjustment="all", feed=None):
        return {s: [(f"2025-{i:02d}", c) for i, c in enumerate(self.hist[s][:-1])] for s in symbols if s in self.hist}

    def latest_prices(self, symbols, feed="iex"):
        return {s: self.px[s] for s in symbols if s in self.px}


class BotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        FakeAlpaca.instances.clear()
        FakeAlpaca.book = {"cash": 1000.0, "pos": {}}
        self.env = {"ALPACA_API_KEY": "k", "ALPACA_SECRET_KEY": "s", "DRY_RUN": "true"}
        self.patches = [mock.patch.object(bot, "Alpaca", FakeAlpaca), mock.patch.dict(os.environ, self.env, clear=False)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def _state(self):
        with open("signals/state.json") as f:
            return json.load(f)

    def test_no_credentials_is_green_noop(self):
        with mock.patch.dict(os.environ, {"ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": ""}):
            self.assertEqual(bot.main(), 0)
        self.assertTrue(os.path.exists("reports/today.md"))
        self.assertFalse(os.path.exists("signals/state.json"))

    def test_outside_window_only_snapshots(self):
        rc = None
        orig_init = FakeAlpaca.__init__

        def closed_init(self, *a, **k):
            orig_init(self, *a, **k)
            self.is_open = False
        with mock.patch.object(FakeAlpaca, "__init__", closed_init):
            rc = bot.main()
        self.assertEqual(rc, 0)
        api = FakeAlpaca.instances[-1]
        self.assertEqual(api.calls, [])
        self.assertTrue(os.path.exists("signals/holdings.json"))
        self.assertNotIn("last_trade_date", self._state())

    def test_first_run_trades_to_targets_and_is_idempotent(self):
        self.assertEqual(bot.main(), 0)
        api = FakeAlpaca.instances[-1]
        st = self._state()
        self.assertEqual(st["last_decision_date"], "2026-09-22")
        self.assertEqual(st["last_trade_date"], "2026-09-22")
        self.assertGreater(len(api.calls), 0)
        buys = sum(v for side, _, v in api.calls if side == "buy")
        self.assertLessEqual(buys, 1000.0 + 1e-6)
        self.assertGreater(buys, 900.0)   # fully invested (momentum or BIL)
        with open("signals/targets.json") as f:
            tj = json.load(f)
        self.assertLessEqual(sum(tj["weights"].values()), 1.0 + 1e-6)
        # holdings match targets (within the min-trade band)
        held = {s: q * api.px[s] for s, q in api.pos.items() if q > 1e-9}
        for s, w in tj["weights"].items():
            self.assertAlmostEqual(held.get(s, 0.0), w * 1000.0, delta=6.0)
        # second run same day: strategy is NOT re-stepped, no new orders
        n_calls = len(api.calls)
        self.assertEqual(bot.main(), 0)
        api2 = FakeAlpaca.instances[-1]
        self.assertEqual(len(api2.calls), 0)
        self.assertEqual(self._state()["strategy"], st["strategy"])

    def test_max_capital_caps_deployment(self):
        with mock.patch.dict(os.environ, {"MAX_CAPITAL": "300"}):
            self.assertEqual(bot.main(), 0)
        api = FakeAlpaca.instances[-1]
        buys = sum(v for side, _, v in api.calls if side == "buy")
        self.assertLessEqual(buys, 300.0 + 1e-6)
        self.assertGreater(buys, 250.0)

    def test_no_trade_mode_submits_nothing(self):
        with mock.patch.dict(os.environ, {"NO_TRADE": "true"}):
            self.assertEqual(bot.main(), 0)
        api = FakeAlpaca.instances[-1]
        self.assertEqual(api.calls, [])
        self.assertTrue(os.path.exists("signals/targets.json"))
        self.assertNotIn("last_trade_date", self._state())

    def test_kill_switch_liquidates_and_halts(self):
        os.makedirs("signals", exist_ok=True)
        with open("signals/state.json", "w") as f:
            json.dump({"hwm": 2000.0}, f)   # equity 1000 is -50% from hwm
        orig_init = FakeAlpaca.__init__

        def with_pos(self, *a, **k):
            orig_init(self, *a, **k)
            self.pos = {"SPY": 2.0}
            self.cash = 1000.0 - 2.0 * self.px["SPY"]
        with mock.patch.object(FakeAlpaca, "__init__", with_pos):
            self.assertEqual(bot.main(), 0)
        api = FakeAlpaca.instances[-1]
        self.assertTrue(self._state()["halted"])
        self.assertEqual(api.pos, {})
        # halted state blocks trading on the next run
        self.assertEqual(bot.main(), 0)
        self.assertEqual(FakeAlpaca.instances[-1].calls, [])

    def test_plan_orders_sells_first_and_closes_zero_targets(self):
        plan = bot.plan_orders({"SPY": 500.0, "GLD": 300.0}, {"SPY": 200.0, "TLT": 150.0}, 5.0)
        kinds = [k for _, k, _ in plan]
        self.assertEqual(kinds[0], "close")
        self.assertEqual(plan[0][0], "TLT")
        self.assertIn(("SPY", "buy", 300.0), plan)
        self.assertIn(("GLD", "buy", 300.0), plan)

    def test_parse_ts_handles_nanoseconds(self):
        d = bot.parse_ts("2026-09-22T15:40:00.123456789-04:00")
        self.assertEqual(d.hour, 15)
        self.assertEqual(d.utcoffset().total_seconds(), -4 * 3600)
        self.assertEqual(bot.parse_ts("2026-09-22T19:40:00Z").tzname(), "UTC")


if __name__ == "__main__":
    unittest.main()
