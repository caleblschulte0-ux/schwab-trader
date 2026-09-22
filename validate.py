"""Validation suite: is the edge real, or did we fit the past?

    python validate.py            -> reports/validation.md

1. Walk-forward: pick parameters on 2008-2016 only (best Sharpe in a grid), then run
   them untouched on 2017-2026. Compares to the shipped defaults on both halves.
2. Parameter sensitivity: Sharpe over a top_n x lookback-set matrix (full period).
3. Timing luck: the weekly rebalance cycle started on 5 different days.
4. Block bootstrap: resample the strategy's daily returns in 21-day blocks into 1,000
   synthetic 5-year paths -> distribution of CAGR and max drawdown.
5. Rolling 3-year windows: how often did the strategy beat SPY, and by how much.
Pure stdlib. ~30 seconds.
"""
from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import replace
from typing import Dict, List, Tuple

import data as datamod
from backtest import SLIPPAGE_BPS, run
from strategy import DEFENSIVE, LEVERAGED, MR_UNIVERSE, UNIVERSE, Params

IS_START, IS_END = "2008-01-01", "2016-12-31"
OOS_START = "2017-01-01"


def daily_returns(curve: List[Tuple[str, float]]) -> List[float]:
    eq = [e for _, e in curve]
    return [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq))]


def stats_from_rets(rets: List[float]) -> Tuple[float, float, float]:
    """(CAGR, Sharpe, MaxDD) from daily returns."""
    if not rets:
        return 0.0, 0.0, 0.0
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        eq *= 1 + r
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    years = len(rets) / 252
    cagr = eq ** (1 / years) - 1 if years > 0 else 0.0
    m = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / max(1, len(rets) - 1))
    return cagr, (m / sd * math.sqrt(252) if sd > 0 else 0.0), mdd


def main() -> int:
    hist = datamod.load_history(sorted(set(UNIVERSE) | set(MR_UNIVERSE) | set(DEFENSIVE) | set(LEVERAGED.values())), max_age_hours=None)
    base = Params()
    L: List[str] = ["# Validation report", "",
                    f"_Same engine as `backtest.py`: close fills, {SLIPPAGE_BPS:.0f} bps slippage/side, $0 commissions, dividends reinvested._", ""]

    # ---------------------------------------------------------------- 1. walk-forward
    grid = []
    for top_n in (4, 6, 8, 10):
        for lbs in ((63, 126, 252), (21, 63, 126, 252), (126, 252), (63, 126)):
            for reb in (5, 10, 21):
                grid.append(replace(base, mom_top_n=top_n, mom_lookbacks=lbs, mom_rebalance_days=reb))
    best = None
    for prm in grid:
        r = run(hist, prm, IS_START, IS_END)
        if best is None or r["sharpe"] > best[0]["sharpe"]:
            best = (r, prm)
    r_is_best, p_best = best
    r_oos_best = run(hist, p_best, OOS_START)
    r_is_def = run(hist, base, IS_START, IS_END)
    r_oos_def = run(hist, base, OOS_START)
    r_full_def = run(hist, base, IS_START)
    L += ["## 1. Walk-forward (out-of-sample) test", "",
          f"Parameters chosen on **{IS_START} → {IS_END}** only (best Sharpe among {len(grid)} combinations), then run untouched on **{OOS_START} → today**.", "",
          "| Parameter set | In-sample CAGR | In-sample Sharpe | **Out-of-sample CAGR** | **Out-of-sample Sharpe** | OOS Max DD | OOS SPY CAGR |",
          "|---|---:|---:|---:|---:|---:|---:|",
          f"| Best in-sample: top {p_best.mom_top_n}, lookbacks {list(p_best.mom_lookbacks)}, rebalance {p_best.mom_rebalance_days}d | {r_is_best['cagr']:+.1%} | {r_is_best['sharpe']:.2f} | {r_oos_best['cagr']:+.1%} | {r_oos_best['sharpe']:.2f} | {r_oos_best['max_drawdown']:.1%} | {r_oos_best['spy']['cagr']:+.1%} |",
          f"| Shipped defaults: top {base.mom_top_n}, lookbacks {list(base.mom_lookbacks)}, rebalance {base.mom_rebalance_days}d | {r_is_def['cagr']:+.1%} | {r_is_def['sharpe']:.2f} | {r_oos_def['cagr']:+.1%} | {r_oos_def['sharpe']:.2f} | {r_oos_def['max_drawdown']:.1%} | {r_oos_def['spy']['cagr']:+.1%} |",
          "", "If the out-of-sample Sharpe collapsed relative to in-sample, the edge was fitted. "
              "A modest decay is normal; a similar number means the rules generalise.", ""]

    # ---------------------------------------------------------------- 2. sensitivity
    lb_sets = [(63, 126, 252), (21, 63, 126, 252), (126, 252), (63, 126), (252,)]
    L += ["## 2. Parameter sensitivity (full period Sharpe)", "",
          "| top_n \\ lookbacks | " + " | ".join(str(list(x)) for x in lb_sets) + " |",
          "|---|" + "---:|" * len(lb_sets)]
    for top_n in (3, 4, 5, 6, 7, 8):
        row = [f"| **{top_n}**"]
        for lbs in lb_sets:
            r = run(hist, replace(base, mom_top_n=top_n, mom_lookbacks=lbs), IS_START)
            mark = "**" if (top_n == base.mom_top_n and tuple(lbs) == tuple(base.mom_lookbacks)) else ""
            row.append(f"{mark}{r['sharpe']:.2f}{mark}")
        L.append(" | ".join(row) + " |")
    L += ["", "A robust strategy shows a plateau, not a single spike. The shipped cell is bold.", ""]

    # ---------------------------------------------------------------- 3. timing luck
    L += ["## 3. Rebalance-timing luck", "", "Same rules, weekly cycle started on five different days:", "",
          "| Start | CAGR | Sharpe | Max DD |", "|---|---:|---:|---:|"]
    tl = []
    for start in ("2008-01-02", "2008-01-03", "2008-01-04", "2008-01-07", "2008-01-08"):
        r = run(hist, base, start)
        tl.append(r["sharpe"])
        L.append(f"| {start} | {r['cagr']:+.1%} | {r['sharpe']:.2f} | {r['max_drawdown']:.1%} |")
    L += ["", f"Sharpe spread across start days: {min(tl):.2f} – {max(tl):.2f}.", ""]

    # ---------------------------------------------------------------- 4. bootstrap
    rets = daily_returns(r_full_def["curve"])
    rnd = random.Random(7)
    block = 21
    horizon = 252 * 5
    n_paths = 1000
    cagrs, mdds = [], []
    blocks = [rets[i:i + block] for i in range(0, len(rets) - block, block)]
    for _ in range(n_paths):
        path: List[float] = []
        while len(path) < horizon:
            path.extend(rnd.choice(blocks))
        c, _, d = stats_from_rets(path[:horizon])
        cagrs.append(c)
        mdds.append(d)
    cagrs.sort()
    mdds.sort()

    def pct(xs, q):
        return xs[min(len(xs) - 1, int(q * len(xs)))]

    L += ["## 4. Block-bootstrap: what a random 5-year stretch could look like", "",
          f"{n_paths} synthetic 5-year paths built from the strategy's own daily returns ({block}-day blocks, order shuffled).", "",
          "| Percentile | 5-yr CAGR | Max drawdown |", "|---|---:|---:|"]
    for q, name in ((0.05, "5th (bad luck)"), (0.25, "25th"), (0.50, "median"), (0.75, "75th"), (0.95, "95th (good luck)")):
        L.append(f"| {name} | {pct(cagrs, q):+.1%} | {pct(mdds, q):.1%} |")
    p20 = sum(1 for d in mdds if d <= -0.20) / n_paths
    p30 = sum(1 for d in mdds if d <= -0.30) / n_paths
    L += ["", f"Probability a 5-year stretch would trip a 20% kill switch: **{p20:.0%}** of paths; a 30% kill switch: **{p30:.0%}**. "
              "That is why the executor's default `MAX_DRAWDOWN_HALT` is 0.30: a halt at 20% would fire inside the strategy's normal "
              "drawdown range and sell the bottom. "
              f"Probability of a negative 5-year CAGR: **{sum(1 for c in cagrs if c < 0) / n_paths:.0%}**.", ""]

    # ---------------------------------------------------------------- 5. rolling windows
    curve = r_full_def["curve"]
    spy_curve = None
    from backtest import SymbolSeries  # noqa: E402
    spy = SymbolSeries("SPY", hist["SPY"], base)
    dates = [d for d, _ in curve]
    eq = [e for _, e in curve]
    spy_eq = [spy.closes[spy.index[d]] if d in spy.index else None for d in dates]
    win = 252 * 3
    beats = 0
    n = 0
    diffs = []
    for i in range(0, len(eq) - win, 21):
        if spy_eq[i] and spy_eq[i + win]:
            s = (eq[i + win] / eq[i]) ** (1 / 3) - 1
            b = (spy_eq[i + win] / spy_eq[i]) ** (1 / 3) - 1
            n += 1
            beats += s > b
            diffs.append(s - b)
    diffs.sort()
    L += ["## 5. Rolling 3-year windows vs SPY", "",
          f"Across {n} overlapping 3-year windows the strategy beat SPY buy-and-hold in **{beats / n:.0%}** of them. "
          f"Median annualised gap {diffs[len(diffs) // 2]:+.1%}; worst {diffs[0]:+.1%}; best {diffs[-1]:+.1%}.", "",
          "This is the number to internalise: it will trail SPY in most straight-up 3-year stretches, "
          "and win by a lot in the stretches that include a bear market.", ""]

    # ---------------------------------------------------------------- overlays
    L += ["## 6. Building blocks and overlays, switched one at a time", "",
          "Everything below is implemented in `strategy.py`; the shipped default is the row marked ✅. "
          "Each row flips ONE thing relative to the shipped defaults (`python backtest.py --grid3` for more).", "",
          "| Variant | 2008→ CAGR / Sharpe / MaxDD | 2015→ CAGR / Sharpe / MaxDD | OOS 2017→ CAGR / Sharpe / MaxDD |", "|---|---|---|---|"]
    variants = [("✅ Shipped defaults", base),
                ("previous defaults (core 30%, top 6, 200-day)", replace(base, core_weight=0.3, mom_top_n=6, mom_hysteresis=2, trend_sma=200)),
                ("no core sleeve (100% rotation)", replace(base, core_weight=0.0)),
                ("fixed SPY core instead of adaptive", replace(base, core_symbol="SPY")),
                ("'growth' preset: fixed QQQ core", replace(base, core_symbol="QQQ")),
                ("'aggressive' preset: 50% in 2x SPY/QQQ (SSO/QLD), trend-timed", replace(base, core_leveraged=True, core_weight=0.5, core_candidates=("SPY", "QQQ"))),
                ("aggressive + 15% vol cap (rejected)", replace(base, core_leveraged=True, core_weight=0.5, core_candidates=("SPY", "QQQ"), vol_target=0.15)),
                ("single rebalance tranche (no stagger)", replace(base, mom_tranches=1)),
                ("no cluster cap", replace(base, cluster_cap=1.0)),
                ("top 5 / weekly (previous defaults)", replace(base, mom_top_n=5, mom_rebalance_days=5)),
                ("defensive asset by momentum (TLT/IEF/GLD)", replace(base, defensive_mode="momentum")),
                ("breadth regime switch (<40% → all defensive)", replace(base, breadth_min=0.4)),
                ("portfolio vol target 12%", replace(base, vol_target=0.12)),
                ("daily rebalance + hysteresis", replace(base, mom_rebalance_days=1)),
                ("+ mean-reversion sleeve 25%", replace(base, mr_weight=0.25, mom_weight=0.75)),
                ("include 1-month lookback", replace(base, mom_lookbacks=(21, 63, 126, 252))),
                ("equal weights instead of inverse-vol", replace(base, mom_weighting="equal"))]
    for name, prm in variants:
        cells = []
        for start in (IS_START, "2015-01-01", OOS_START):
            r = run(hist, prm, start)
            cells.append(f"{r['cagr']:+.1%} / {r['sharpe']:.2f} / {r['max_drawdown']:.0%}")
        L.append(f"| {name} | " + " | ".join(cells) + " |")
    L += ["", "_Past performance is not a promise of future results._"]

    os.makedirs("reports", exist_ok=True)
    with open("reports/validation.md", "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
