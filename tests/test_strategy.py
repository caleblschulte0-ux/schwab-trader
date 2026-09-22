"""Unit tests for the strategy engine. Run: python -m unittest discover -s tests -v"""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy import (MR_UNIVERSE, UNIVERSE, MRPosition, Params, State, annual_vol, compute_signals,
                      compute_targets, momentum_score, rsi, sma)


def synth(seed: int, n: int = 400, drift: float = 0.0004, vol: float = 0.01, start: float = 100.0):
    rnd = random.Random(seed)
    closes = [start]
    for _ in range(n - 1):
        closes.append(closes[-1] * math.exp(drift + vol * rnd.gauss(0, 1)))
    return closes


class IndicatorTests(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4], 2), 3.5)
        self.assertIsNone(sma([1, 2], 3))

    def test_rsi_bounds_and_direction(self):
        up = [100 + i for i in range(30)]
        down = [100 - i for i in range(30)]
        self.assertEqual(rsi(up, 2), 100.0)
        self.assertEqual(rsi(down, 2), 0.0)
        r = rsi(synth(1), 2)
        self.assertTrue(0 <= r <= 100)

    def test_momentum_score(self):
        closes = [100.0] * 253 + [110.0]
        # 10% over every lookback
        self.assertAlmostEqual(momentum_score(closes, (63, 126, 252)), 0.10, places=9)
        self.assertIsNone(momentum_score([1.0] * 10, (63,)))

    def test_annual_vol(self):
        v = annual_vol(synth(2, 300, 0.0, 0.01), 63)
        self.assertTrue(0.05 < v < 0.35)  # ~1%/day -> ~16%/yr


class TargetTests(unittest.TestCase):
    def _hist(self, seed=3, n=400):
        rnd = random.Random(seed)
        hist = {}
        for s in UNIVERSE + ["BIL"]:
            drift = rnd.uniform(-0.0008, 0.0012)
            hist[s] = synth(rnd.randint(0, 10_000), n, drift, 0.012 if s != "BIL" else 0.0002)
        return hist

    def test_weights_sum_leq_one_and_capped(self):
        dec = compute_targets(self._hist(), State(), Params(), today="2026-01-02")
        total = sum(dec.weights.values())
        self.assertLessEqual(total, 1.0 + 1e-9)
        for s, w in dec.weights.items():
            self.assertLessEqual(w, Params().max_position_weight + 1e-9)
            self.assertGreater(w, 0)

    def test_first_run_rebalances_and_selects_top_n(self):
        p = Params()
        dec = compute_targets(self._hist(), State(), p, today="2026-01-02")
        self.assertTrue(dec.rebalanced_momentum)
        self.assertLessEqual(len(dec.mom_selected), p.mom_top_n)
        self.assertEqual(dec.state.mom_days_since_rebalance, 0)

    def test_no_rebalance_between_weeks(self):
        p = Params()
        hist = self._hist()
        dec1 = compute_targets(hist, State(), p, today="2026-01-02")
        dec2 = compute_targets(hist, dec1.state, p, today="2026-01-05")
        self.assertFalse(dec2.rebalanced_momentum)
        self.assertEqual(dec2.mom_selected, dec1.mom_selected)

    def test_bear_market_goes_to_cash_proxy(self):
        # everything trending down -> nothing eligible -> 100% cash proxy
        hist = {s: synth(7, 400, -0.002, 0.01) for s in UNIVERSE}
        hist["BIL"] = synth(8, 400, 0.0001, 0.0002)
        dec = compute_targets(hist, State(), Params(), today="2026-01-02")
        self.assertEqual(dec.mom_selected, [])
        self.assertAlmostEqual(dec.weights.get("BIL", 0.0), 1.0, places=6)

    def test_cash_when_no_proxy(self):
        hist = {s: synth(7, 400, -0.002, 0.01) for s in UNIVERSE}
        dec = compute_targets(hist, State(), Params(cash_proxy=None), today="2026-01-02")
        self.assertEqual(dec.weights, {})

    def test_mean_reversion_sleeve_when_enabled(self):
        p = Params(mr_weight=0.4, mom_weight=0.6)
        hist = self._hist()
        # force an oversold-in-uptrend setup for SPY: long uptrend then two sharp down days
        spy = [100 * math.exp(0.001 * i) for i in range(400)]
        spy[-2] = spy[-3] * 0.97
        spy[-1] = spy[-2] * 0.97
        hist["SPY"] = spy
        dec = compute_targets(hist, State(), p, today="2026-01-02")
        self.assertIn("SPY", dec.mr_open)
        self.assertGreaterEqual(dec.weights["SPY"], p.mr_weight / p.mr_max_positions - 1e-9)
        # exit on snap-back above the 5-day SMA
        spy2 = spy + [spy[-1] * 1.08]
        hist["SPY"] = spy2
        dec2 = compute_targets(hist, dec.state, p, today="2026-01-05")
        self.assertNotIn("SPY", dec2.mr_open)
        self.assertTrue(any("MR exit SPY" in n for n in dec2.notes))

    def test_mr_disabled_releases_positions(self):
        st = State(mr_positions={"SPY": MRPosition("SPY", "2026-01-01", 100.0)})
        dec = compute_targets(self._hist(), st, Params(mr_weight=0.0), today="2026-01-02")
        self.assertEqual(dec.mr_open, [])

    def test_state_roundtrip(self):
        st = State(mom_holdings=["SPY", "GLD"], mom_days_since_rebalance=3,
                   mr_positions={"QQQ": MRPosition("QQQ", "2026-01-01", 400.0, 2)})
        st2 = State.from_dict(st.to_dict())
        self.assertEqual(st2.mom_holdings, ["SPY", "GLD"])
        self.assertEqual(st2.mom_days_since_rebalance, 3)
        self.assertEqual(st2.mr_positions["QQQ"].entry_price, 400.0)
        self.assertEqual(st2.mr_positions["QQQ"].days_held, 2)

    def test_pure_no_mutation_of_input_state(self):
        st = State()
        compute_targets(self._hist(), st, Params(), today="2026-01-02")
        self.assertEqual(st.mom_holdings, [])
        self.assertEqual(st.mom_days_since_rebalance, 9999)


class BacktestParityTests(unittest.TestCase):
    """The backtester's incremental indicators must match strategy.compute_signals."""

    def test_signals_match(self):
        from backtest import SymbolSeries
        p = Params()
        closes = synth(11, 700, 0.0003, 0.012)
        bars = [(f"d{i}", c) for i, c in enumerate(closes)]
        ss = SymbolSeries("X", bars, p)
        for i in (300, 450, 699):
            fast = ss.signals_at(i)
            slow = compute_signals(closes[: i + 1], p)
            self.assertAlmostEqual(fast.sma_trend, slow.sma_trend, places=8)
            self.assertAlmostEqual(fast.sma_exit, slow.sma_exit, places=8)
            self.assertAlmostEqual(fast.mom_score, slow.mom_score, places=8)
            self.assertAlmostEqual(fast.vol, slow.vol, places=6)
            self.assertAlmostEqual(fast.rsi, slow.rsi, places=4)


if __name__ == "__main__":
    unittest.main()
