"""SimBroker unit tests + the executor running end-to-end on the simulator (no network)."""
import json
import math
import os
import random
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot
from broker_sim import SimBroker
from strategy import DEFENSIVE, LEVERAGED, UNIVERSE


def synth(seed, n=400, drift=0.0005, vol=0.01, start=100.0):
    rnd = random.Random(seed)
    c = [start]
    for _ in range(n - 1):
        c.append(c[-1] * math.exp(drift + vol * rnd.gauss(0, 1)))
    return c


def trading_dates(n, last="2026-09-22"):
    """n consecutive weekdays ending on `last` (oldest first)."""
    from datetime import date, timedelta
    d = date.fromisoformat(last)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return out[::-1]


def fake_history(seed=5, n=400):
    rnd = random.Random(seed)
    dates = trading_dates(n)
    out = {}
    for s in sorted(set(UNIVERSE) | set(DEFENSIVE) | set(LEVERAGED.values())):
        closes = synth(rnd.randint(0, 9999), n, rnd.uniform(-0.0005, 0.0015), 0.0002 if s == "BIL" else 0.012)
        out[s] = list(zip(dates, closes))
    return out


NOW = datetime(2026, 9, 22, 19, 40, tzinfo=timezone.utc)  # 15:40 ET, market open


class SimBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "sim.json")
        self.api = SimBroker(path=self.path, start_cash=1000.0, history=fake_history(), now=NOW)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_clock_open_and_closed(self):
        c = self.api.clock()
        self.assertTrue(c["is_open"])
        self.assertTrue(c["next_close"].startswith("2026-09-22T16:00:00"))
        closed = SimBroker(path=self.path, history=fake_history(), now=datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc))  # Saturday
        c2 = closed.clock()
        self.assertFalse(c2["is_open"])
        self.assertTrue(c2["next_open"].startswith("2026-09-28T09:30:00"))

    def test_buy_sell_roundtrip_and_persistence(self):
        o = self.api.submit_order("SPY", "buy", notional=300.0)
        self.assertEqual(o["status"], "filled")
        acct = self.api.account()
        self.assertAlmostEqual(float(acct["cash"]), 700.0, places=2)
        self.assertLess(float(acct["equity"]), 1000.0)      # paid slippage
        self.assertGreater(float(acct["equity"]), 999.0)
        pos = self.api.positions()
        self.assertEqual(pos[0]["symbol"], "SPY")
        self.api.close_position("SPY")
        self.assertEqual(self.api.positions(), [])
        self.assertEqual(len(self.api.fills()), 2)
        # reload from disk
        api2 = SimBroker(path=self.path, history=fake_history(), now=NOW)
        self.assertEqual(len(api2.fills()), 2)
        self.assertAlmostEqual(float(api2.account()["cash"]), float(self.api.account()["cash"]), places=6)

    def test_cannot_overspend(self):
        with self.assertRaises(RuntimeError):
            self.api.submit_order("SPY", "buy", notional=5000.0)

    def test_snapshot_and_history(self):
        self.api.snapshot()
        self.api.snapshot()  # same day -> one point
        h = self.api.portfolio_history()
        self.assertEqual(len(h["equity"]), 1)
        self.assertAlmostEqual(h["equity"][0], 1000.0, places=2)

    def test_latest_prices_require_todays_bar(self):
        hist = fake_history()
        for s in hist:
            hist[s] = hist[s][:-1]          # newest bar is yesterday (pre-market / seed fallback)
        api = SimBroker(path=self.path, history=hist, now=NOW)
        self.assertEqual(api.latest_prices(["SPY", "QQQ"]), {})

    def test_daily_bars_and_latest(self):
        bars = self.api.daily_bars(["SPY"], start="2025-01-01", end="2026-09-21")
        self.assertTrue(all(d <= "2026-09-21" for d, _ in bars["SPY"]))
        self.assertIn("SPY", self.api.latest_prices(["SPY", "NOPE"]))
        self.assertNotIn("NOPE", self.api.latest_prices(["SPY", "NOPE"]))


class ExecutorOnSimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        shutil.copy(os.path.join(self.cwd, "config.json"), "config.json")
        hist = fake_history()

        class TestSim(SimBroker):
            def __init__(self, path=os.path.join("signals", "sim_account.json"), start_cash=1000.0, history=None, now=None):
                super().__init__(path=path, start_cash=start_cash, history=hist, now=NOW)
        self.patches = [mock.patch.object(bot, "SimBroker", TestSim),
                        mock.patch.object(bot.datamod, "load_history", side_effect=AssertionError("network call in test")),
                        mock.patch.dict(os.environ, {"ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": ""})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)

    def test_runs_end_to_end_without_keys(self):
        self.assertEqual(bot.main(), 0)
        with open("signals/sim_account.json") as f:
            book = json.load(f)
        self.assertGreater(len(book["fills"]), 0)
        self.assertLess(book["cash"], 20.0)                  # fully deployed
        self.assertEqual(len(book["equity_curve"]), 1)
        with open("signals/holdings.json") as f:
            h = json.load(f)
        self.assertEqual(h["mode"], "sim")
        with open("signals/targets.json") as f:
            t = json.load(f)
        self.assertEqual(t["preset"], json.load(open("config.json"))["preset"])
        self.assertIn("regime", t)
        # second run same day: reconciles only, no meaningful new orders
        n = len(book["fills"])
        self.assertEqual(bot.main(), 0)
        with open("signals/sim_account.json") as f:
            book2 = json.load(f)
        self.assertLessEqual(len(book2["fills"]) - n, 2)

    def test_config_preset_and_env_override(self):
        with open("config.json") as f:
            cfg = json.load(f)
        cfg["preset"] = "growth"
        cfg["executor"]["max_capital"] = 500
        with open("config.json", "w") as f:
            json.dump(cfg, f)
        self.assertEqual(bot.main(), 0)
        with open("signals/targets.json") as f:
            t = json.load(f)
        self.assertEqual(t["preset"], "growth")
        self.assertEqual(t["capital"], 500)
        with open("signals/sim_account.json") as f:
            book = json.load(f)
        self.assertGreater(book["cash"], 480.0)              # only $500 deployed

    def test_aggressive_preset_holds_2x_core_and_widens_halt(self):
        import config as cfgmod
        with open("config.json") as f:
            cfg = json.load(f)
        cfg["preset"] = "aggressive"
        with open("config.json", "w") as f:
            json.dump(cfg, f)
        self.assertEqual(cfgmod.executor_settings(cfg)["max_drawdown_halt"], 0.45)
        with mock.patch.dict(os.environ, {"MAX_DRAWDOWN_HALT": "0.4"}):
            self.assertEqual(cfgmod.executor_settings(cfg)["max_drawdown_halt"], 0.4)   # env wins
        self.assertEqual(bot.main(), 0)
        with open("signals/targets.json") as f:
            t = json.load(f)
        core = t["regime"]["core"]
        if core is not None:
            self.assertIn(core, ("SSO", "QLD"))
            self.assertAlmostEqual(t["weights"][core], 0.5, places=4)

    def test_unknown_config_key_is_fatal(self):
        with open("config.json") as f:
            cfg = json.load(f)
        cfg["strategy"] = {"mom_topn": 3}
        with open("config.json", "w") as f:
            json.dump(cfg, f)
        with self.assertRaises(ValueError):
            bot.main()


if __name__ == "__main__":
    unittest.main()
