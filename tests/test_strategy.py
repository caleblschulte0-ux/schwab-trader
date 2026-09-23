"""Unit tests for the strategy engine. Run: python -m unittest discover -s tests -v"""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy import (MR_UNIVERSE, UNIVERSE, MRPosition, Params, State, annual_vol, compute_signals,
                      compute_targets, momentum_score, rsi, sma)
P1 = Params(mom_tranches=1)


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
        p = Params()
        dec = compute_targets(self._hist(), State(), p, today="2026-01-02")
        total = sum(dec.weights.values())
        self.assertLessEqual(total, 1.0 + 1e-9)
        for s, w in dec.weights.items():
            if s != p.cash_proxy and s != dec.regime.get("core"):  # cash proxy and core sleeve are sized on purpose
                self.assertLessEqual(w, p.max_position_weight + 1e-9)
            self.assertGreater(w, 0)

    def test_first_run_rebalances_and_selects_top_n(self):
        p = Params()
        dec = compute_targets(self._hist(), State(), p, today="2026-01-02")
        self.assertTrue(dec.rebalanced_momentum)
        self.assertLessEqual(len(dec.mom_selected), p.mom_top_n)
        self.assertEqual(dec.state.mom_days_since_rebalance, 0)

    def test_no_rebalance_between_weeks(self):
        p = P1
        hist = self._hist()
        dec1 = compute_targets(hist, State(), p, today="2026-01-02")
        dec2 = compute_targets(hist, dec1.state, p, today="2026-01-05")
        self.assertFalse(dec2.rebalanced_momentum)
        self.assertEqual(dec2.mom_selected, dec1.mom_selected)

    def test_tranches_full_entry_then_staggered(self):
        p = Params(mom_tranches=5, mom_rebalance_days=10)
        hist = self._hist()
        d1 = compute_targets(hist, State(), p, today="d1")
        self.assertEqual(len(d1.state.tranches), 5)
        self.assertTrue(d1.rebalanced_momentum)
        # day one: every tranche invested (no under-investment during warm-up)
        self.assertTrue(all(tr.holdings for tr in d1.state.tranches))
        self.assertEqual([tr.days_since_rebalance for tr in d1.state.tranches], [0, 2, 4, 6, 8])
        # then the clocks are staggered: only one tranche comes due at a time
        due_days = []
        st = d1.state
        for day in range(2, 13):
            d = compute_targets(hist, st, p, today=f"d{day}")
            st = d.state
            if d.rebalanced_momentum:
                due_days.append(day)
        self.assertEqual(due_days, [3, 5, 7, 9, 11])
        # persistence round-trip keeps tranche clocks
        st2 = State.from_dict(st.to_dict())
        self.assertEqual([t.days_since_rebalance for t in st2.tranches], [t.days_since_rebalance for t in st.tranches])

    def test_tranche_migration_keeps_holdings(self):
        # a single-tranche state upgraded to 5 tranches must not dump its book
        p = Params(mom_tranches=5)
        hist = self._hist()
        d0 = compute_targets(hist, State(), Params(mom_tranches=1), today="d0")
        held = set(d0.mom_selected)
        d1 = compute_targets(hist, d0.state, p, today="d1")
        self.assertTrue(held & set(d1.mom_selected))
        self.assertTrue(all(tr.holdings for tr in d1.state.tranches))

    def test_adaptive_core_picks_strongest(self):
        p = Params(core_symbol="auto", core_candidates=("SPY", "QQQ", "EFA"), core_weight=0.3)
        hist = self._hist()
        # make QQQ the runaway leader and SPY/EFA broken
        hist["QQQ"] = [100 * math.exp(0.002 * i) for i in range(400)]
        hist["SPY"] = [100 * math.exp(-0.001 * i) for i in range(400)]
        hist["EFA"] = [100 * math.exp(-0.001 * i) for i in range(400)]
        dec = compute_targets(hist, State(), p, today="d1")
        self.assertEqual(dec.regime.get("core"), "QQQ")
        self.assertGreaterEqual(dec.weights["QQQ"], 0.3 - 1e-9)
        # all candidates broken -> no core, capital goes defensive
        hist["QQQ"] = hist["SPY"]
        dec2 = compute_targets(hist, State(), p, today="d1")
        self.assertIsNone(dec2.regime.get("core"))

    def test_leveraged_core_uses_underlying_trend(self):
        p = Params(core_leveraged=True, core_weight=0.5, core_symbol="auto", core_candidates=("SPY", "QQQ"))
        hist = self._hist()
        hist["QQQ"] = [100 * math.exp(0.002 * i) for i in range(400)]
        hist["SPY"] = [100 * math.exp(-0.001 * i) for i in range(400)]
        hist["QLD"] = [100 * math.exp(0.004 * i) for i in range(400)]
        hist["SSO"] = [100 * math.exp(-0.002 * i) for i in range(400)]
        dec = compute_targets(hist, State(), p, today="d1")
        self.assertEqual(dec.regime["core"], "QLD")
        self.assertAlmostEqual(dec.weights["QLD"], 0.5, places=6)   # not clipped by the 35% cap
        self.assertLessEqual(sum(dec.weights.values()), 1.0 + 1e-9)
        # underlying breaks trend -> leveraged fund is dropped even if its own chart looks fine
        hist["QQQ"] = [100 * math.exp(-0.001 * i) for i in range(400)]
        dec2 = compute_targets(hist, State(), p, today="d1")
        self.assertNotIn("QLD", dec2.weights)
        self.assertIsNone(dec2.regime["core"])

    def test_core_overlapping_momentum_pick_is_not_clipped(self):
        # QQQ is both the core pick and the top momentum pick: the core's 50% must survive
        p = Params(core_weight=0.5, core_symbol="QQQ", mom_top_n=3)
        hist = self._hist()
        hist["QQQ"] = [100 * math.exp(0.004 * i) for i in range(400)]
        dec = compute_targets(hist, State(), p, today="d1")
        self.assertIn("QQQ", dec.mom_selected)
        self.assertGreaterEqual(dec.weights["QQQ"], 0.5 - 1e-6)
        self.assertLessEqual(dec.weights["QQQ"], 0.5 + p.max_position_weight + 1e-6)
        self.assertLessEqual(sum(dec.weights.values()), 1.0 + 1e-9)

    def test_credit_stress_scales_risk_assets(self):
        from strategy import add_credit_series
        p = Params(credit_filter=True, credit_sma=50, credit_scale=0.5)
        hist = self._hist()
        hist["IEF"] = [100.0] * 400
        hist["HYG"] = [100.0] * 380 + [100.0 - 2 * i for i in range(1, 21)]   # junk bonds sliding
        add_credit_series(hist)
        dec = compute_targets(hist, State(), p, today="d1")
        self.assertTrue(dec.regime["credit_stress"])
        risk = sum(w for s, w in dec.weights.items() if s not in ("BIL", "SHY", "IEF", "TLT", "GLD"))
        self.assertLessEqual(risk, 0.5 + 1e-6)
        hist["HYG"] = [100.0 + 0.1 * i for i in range(400)]                   # healthy credit
        add_credit_series(hist)
        self.assertFalse(compute_targets(hist, State(), p, today="d1").regime["credit_stress"])

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
