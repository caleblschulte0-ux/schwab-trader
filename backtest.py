"""Backtester for strategy.py on daily adjusted closes.

    python backtest.py                     # full run since 2008, all sleeves
    python backtest.py --start 2015-01-01  # sub-period
    python backtest.py --grid              # robustness grid (is the edge a knife-edge?)
    python backtest.py --refresh           # re-download data

Assumptions (deliberately conservative):
  * Signals computed on the close, fills AT that close (the live bot runs in the last
    hour of the session, so this is close to reality) with SLIPPAGE_BPS per side.
  * Zero commissions (Alpaca). Cash earns 0% (live cash actually earns interest).
  * Dividends are included via adjusted closes.
Pure stdlib; ~1 minute for 18 years x 34 symbols.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import replace
from typing import Dict, List, Optional, Tuple

import data as datamod
from strategy import (DEFENSIVE, LEVERAGED, MR_UNIVERSE, UNIVERSE, Params, Signals, State, compute_targets)

SLIPPAGE_BPS = 5.0


# ----------------------------------------------------------------------------- #
# Fast incremental indicators (same formulas as strategy.compute_signals)         #
# ----------------------------------------------------------------------------- #
class SymbolSeries:
    def __init__(self, sym: str, bars: List[Tuple[str, float]], p: Params):
        self.sym = sym
        self.dates = [d for d, _ in bars]
        self.closes = [c for _, c in bars]
        self.index = {d: i for i, d in enumerate(self.dates)}
        n = len(self.closes)
        self.p = p
        # prefix sums for SMAs
        pref = [0.0] * (n + 1)
        for i, c in enumerate(self.closes):
            pref[i + 1] = pref[i] + c
        self.pref = pref
        self.rets = [0.0] * n
        for i in range(1, n):
            self.rets[i] = self.closes[i] / self.closes[i - 1] - 1.0 if self.closes[i - 1] > 0 else 0.0
        # log returns prefix sums for vol
        lr = [0.0] * n
        for i in range(1, n):
            a, b = self.closes[i - 1], self.closes[i]
            lr[i] = math.log(b / a) if a > 0 and b > 0 else 0.0
        self.lr_sum = [0.0] * (n + 1)
        self.lr_sq = [0.0] * (n + 1)
        for i in range(n):
            self.lr_sum[i + 1] = self.lr_sum[i] + lr[i]
            self.lr_sq[i + 1] = self.lr_sq[i] + lr[i] * lr[i]
        # Wilder RSI computed sequentially over the whole series
        self.rsi = [None] * n
        k = p.mr_rsi_period
        if n > k:
            g = l = 0.0
            for i in range(1, k + 1):
                ch = self.closes[i] - self.closes[i - 1]
                g += max(ch, 0.0); l += max(-ch, 0.0)
            ag, al = g / k, l / k
            self.rsi[k] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
            for i in range(k + 1, n):
                ch = self.closes[i] - self.closes[i - 1]
                ag = (ag * (k - 1) + max(ch, 0.0)) / k
                al = (al * (k - 1) + max(-ch, 0.0)) / k
                self.rsi[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)

    def _sma(self, i: int, n: int) -> Optional[float]:
        if i + 1 < n:
            return None
        return (self.pref[i + 1] - self.pref[i + 1 - n]) / n

    def signals_at(self, i: int) -> Signals:
        p = self.p
        c = self.closes[i]
        mom = None
        if i >= max(p.mom_lookbacks):
            rets = [c / self.closes[i - lb] - 1.0 for lb in p.mom_lookbacks]
            mom = sum(rets) / len(rets)
        vol = None
        n = p.vol_lookback
        if i >= n:
            s = self.lr_sum[i + 1] - self.lr_sum[i + 1 - n]
            sq = self.lr_sq[i + 1] - self.lr_sq[i + 1 - n]
            m = s / n
            var = (sq - n * m * m) / (n - 1)
            vol = math.sqrt(max(var, 0.0)) * math.sqrt(252)
        return Signals(
            close=c,
            sma_trend=self._sma(i, p.trend_sma),
            sma_exit=self._sma(i, p.mr_exit_sma),
            rsi=self.rsi[i],
            mom_score=mom,
            vol=vol,
            n_bars=i + 1,
            rets=self.rets[i + 1 - n:i + 1] if i >= n else (),
            sma_credit=self._sma(i, p.credit_sma),
        )


# ----------------------------------------------------------------------------- #
# Simulation                                                                      #
# ----------------------------------------------------------------------------- #
def run(hist: Dict[str, List[Tuple[str, float]]], p: Params, start: str, end: Optional[str] = None,
        start_equity: float = 1000.0, verbose: bool = False) -> dict:
    from strategy import add_credit_series
    hist = dict(hist)
    add_credit_series(hist, dated=True)
    series = {s: SymbolSeries(s, bars, p) for s, bars in hist.items() if len(bars) > p.min_history}
    calendar = sorted(set(series["SPY"].dates))
    calendar = [d for d in calendar if d >= start and (end is None or d <= end)]

    state = State()
    holdings: Dict[str, float] = {}   # symbol -> dollars
    cash = start_equity
    equity_curve: List[Tuple[str, float]] = []
    trades: List[dict] = []           # MR round trips + momentum swaps, for stats
    last_close: Dict[str, float] = {}
    turnover_total = 0.0
    mr_entry: Dict[str, Tuple[str, float]] = {}

    for d in calendar:
        # 1) mark to market with today's close
        for s in list(holdings):
            ss = series[s]
            i = ss.index.get(d)
            if i is None:
                continue
            prev = last_close.get(s)
            if prev:
                holdings[s] *= ss.closes[i] / prev
            last_close[s] = ss.closes[i]
        equity = cash + sum(holdings.values())

        # 2) signals for everything that has a bar today
        sig: Dict[str, Signals] = {}
        for s, ss in series.items():
            i = ss.index.get(d)
            if i is not None:
                sig[s] = ss.signals_at(i)
                last_close[s] = ss.closes[i]

        # 3) decide
        prev_mr = dict(state.mr_positions)
        dec = compute_targets(None, state, p, today=d, signals=sig)
        state = dec.state

        # MR round-trip bookkeeping
        for s, pos in prev_mr.items():
            if s not in state.mr_positions and s in sig:
                ep = pos.entry_price
                trades.append({"sym": s, "sleeve": "MR", "entry": pos.entry_date, "exit": d,
                               "ret": sig[s].close / ep - 1.0, "days": pos.days_held})

        # 4) rebalance to targets at the close, pay slippage on turnover
        targets = {s: w * equity for s, w in dec.weights.items()}
        for s in set(holdings) | set(targets):
            cur = holdings.get(s, 0.0)
            tgt = targets.get(s, 0.0)
            delta = tgt - cur
            if abs(delta) < 1.0:
                continue
            cost = abs(delta) * SLIPPAGE_BPS / 10_000
            cash -= delta + cost
            turnover_total += abs(delta)
            if tgt <= 0:
                holdings.pop(s, None)
            else:
                holdings[s] = tgt
        equity = cash + sum(holdings.values())
        equity_curve.append((d, equity))
        if verbose and dec.notes:
            print(d, f"eq={equity:,.0f}", "; ".join(dec.notes))

    return summarize(equity_curve, trades, turnover_total, start_equity, series, calendar)


def summarize(curve, trades, turnover, start_equity, series, calendar) -> dict:
    if not curve:
        return {}
    dates = [d for d, _ in curve]
    eq = [e for _, e in curve]
    years = (len(eq)) / 252.0
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1 if years > 0 else 0.0
    rets = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq))]
    m = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    sharpe = (m / sd) * math.sqrt(252) if sd > 0 else 0.0
    downs = [r for r in rets if r < 0]
    dsd = math.sqrt(sum(r * r for r in downs) / len(rets)) if downs else 0.0
    sortino = (m / dsd) * math.sqrt(252) if dsd > 0 else 0.0
    peak = eq[0]; mdd = 0.0; mdd_date = dates[0]
    for d, e in zip(dates, eq):
        peak = max(peak, e)
        dd = e / peak - 1
        if dd < mdd:
            mdd, mdd_date = dd, d
    # yearly returns
    yearly: Dict[str, float] = {}
    first_of_year: Dict[str, float] = {}
    last_of_year: Dict[str, float] = {}
    for d, e in zip(dates, eq):
        y = d[:4]
        first_of_year.setdefault(y, e)
        last_of_year[y] = e
    prev_end = None
    for y in sorted(first_of_year):
        base = prev_end if prev_end is not None else first_of_year[y]
        yearly[y] = last_of_year[y] / base - 1
        prev_end = last_of_year[y]
    # SPY benchmark over the same dates
    spy = series["SPY"]
    spy_eq = []
    for d in dates:
        i = spy.index.get(d)
        spy_eq.append(spy.closes[i] if i is not None else (spy_eq[-1] if spy_eq else None))
    spy_cagr = (spy_eq[-1] / spy_eq[0]) ** (1 / years) - 1
    spk = spy_eq[0]; spy_mdd = 0.0
    for e in spy_eq:
        spk = max(spk, e); spy_mdd = min(spy_mdd, e / spk - 1)
    spy_rets = [spy_eq[i] / spy_eq[i - 1] - 1 for i in range(1, len(spy_eq))]
    sm = sum(spy_rets) / len(spy_rets)
    ssd = math.sqrt(sum((r - sm) ** 2 for r in spy_rets) / (len(spy_rets) - 1))
    spy_sharpe = (sm / ssd) * math.sqrt(252) if ssd > 0 else 0.0
    spy_yearly: Dict[str, float] = {}
    fy: Dict[str, float] = {}; ly: Dict[str, float] = {}
    for d, e in zip(dates, spy_eq):
        fy.setdefault(d[:4], e); ly[d[:4]] = e
    pe = None
    for y in sorted(fy):
        base = pe if pe is not None else fy[y]
        spy_yearly[y] = ly[y] / base - 1; pe = ly[y]

    # ---- loss-frequency metrics (what "loses money less often" means, measured)
    month_end: Dict[str, float] = {}
    for d, e in zip(dates, eq):
        month_end[d[:7]] = e
    mkeys = sorted(month_end)
    mrets = [month_end[mkeys[i]] / month_end[mkeys[i - 1]] - 1 for i in range(1, len(mkeys))]
    losing_months = sum(1 for x in mrets if x < 0) / len(mrets) if mrets else 0.0
    r12 = [eq[i] / eq[i - 252] - 1 for i in range(252, len(eq), 5)]
    losing_12m = sum(1 for x in r12 if x < 0) / len(r12) if r12 else 0.0
    worst_12m = min(r12) if r12 else 0.0
    peak = eq[0]; under = 0; longest = 0; days_under = 0
    for e in eq:
        if e >= peak:
            peak = e; under = 0
        else:
            under += 1; days_under += 1; longest = max(longest, under)
    losing_years = sum(1 for v in yearly.values() if v < 0) / len(yearly) if yearly else 0.0

    mr = [t for t in trades if t["sleeve"] == "MR"]
    wins = [t for t in mr if t["ret"] > 0]
    return {
        "losing_months": losing_months, "losing_12m": losing_12m, "worst_12m": worst_12m,
        "longest_underwater_days": longest, "time_underwater": days_under / len(eq), "losing_years": losing_years,
        "start": dates[0], "end": dates[-1], "years": round(years, 2),
        "start_equity": start_equity, "end_equity": round(eq[-1], 2),
        "cagr": cagr, "vol": sd * math.sqrt(252), "sharpe": sharpe, "sortino": sortino,
        "max_drawdown": mdd, "max_drawdown_date": mdd_date,
        "calmar": (cagr / -mdd) if mdd < 0 else 0.0,
        "annual_turnover": turnover / start_equity / years if years else 0.0,  # rough, in start-equity units
        "yearly": yearly,
        "spy": {"cagr": spy_cagr, "max_drawdown": spy_mdd, "sharpe": spy_sharpe, "yearly": spy_yearly},
        "mr_trades": len(mr),
        "mr_win_rate": (len(wins) / len(mr)) if mr else 0.0,
        "mr_avg_ret": (sum(t["ret"] for t in mr) / len(mr)) if mr else 0.0,
        "mr_avg_days": (sum(t["days"] for t in mr) / len(mr)) if mr else 0.0,
        "curve": curve,
    }


def fmt_report(r: dict, title: str = "Backtest") -> str:
    L = [f"# {title}", "",
         f"Period: {r['start']} -> {r['end']} ({r['years']} yrs)   start ${r['start_equity']:,.0f} -> end ${r['end_equity']:,.0f}", "",
         "| Metric | Strategy | SPY buy&hold |", "|---|---:|---:|",
         f"| CAGR | {r['cagr']:+.1%} | {r['spy']['cagr']:+.1%} |",
         f"| Annual vol | {r['vol']:.1%} | - |",
         f"| Sharpe (rf=0) | {r['sharpe']:.2f} | {r['spy']['sharpe']:.2f} |",
         f"| Sortino | {r['sortino']:.2f} | - |",
         f"| Max drawdown | {r['max_drawdown']:.1%} ({r['max_drawdown_date']}) | {r['spy']['max_drawdown']:.1%} |",
         f"| Calmar | {r['calmar']:.2f} | - |",
         f"| Losing months | {r['losing_months']:.0%} | - |",
         f"| Losing 12-month stretches | {r['losing_12m']:.0%} (worst {r['worst_12m']:+.1%}) | - |",
         f"| Losing calendar years | {r['losing_years']:.0%} | - |",
         f"| Longest time below a previous high | {r['longest_underwater_days'] / 21:.0f} months | - |",
         f"| MR round-trips | {r['mr_trades']} (win {r['mr_win_rate']:.0%}, avg {r['mr_avg_ret']:+.2%}, {r['mr_avg_days']:.1f}d) | - |",
         "", "| Year | Strategy | SPY |", "|---|---:|---:|"]
    for y in sorted(r["yearly"]):
        L.append(f"| {y} | {r['yearly'][y]:+.1%} | {r['spy']['yearly'].get(y, 0):+.1%} |")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2008-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--grid2", action="store_true", help="structural variants")
    ap.add_argument("--grid3", action="store_true", help="risk-overlay variants")
    ap.add_argument("--grid4", action="store_true", help="candidate defaults confirmation")
    ap.add_argument("--grid5", action="store_true", help="tranches + adaptive core")
    ap.add_argument("--grid6", action="store_true", help="leveraged core")
    ap.add_argument("--grid7", action="store_true", help="loss-frequency search")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--out", default="reports/backtest.md")
    ap.add_argument("--curve", default=None, help="write equity curve CSV here")
    args = ap.parse_args()

    hist = datamod.load_history(sorted(set(UNIVERSE) | set(MR_UNIVERSE) | set(DEFENSIVE) | set(LEVERAGED.values())), refresh=args.refresh, max_age_hours=None)
    if "SPY" not in hist:
        print("need SPY history"); return 1

    if args.grid:
        base = Params()
        grid = [
            ("baseline", base),
            ("mom_top_n=3", replace(base, mom_top_n=3)),
            ("mom_top_n=7", replace(base, mom_top_n=7)),
            ("rebalance=monthly", replace(base, mom_rebalance_days=21)),
            ("rsi_entry=5", replace(base, mr_rsi_entry=5)),
            ("rsi_entry=15", replace(base, mr_rsi_entry=15)),
            ("mr_weight=0.25", replace(base, mr_weight=0.25, mom_weight=0.75)),
            ("mr_weight=0.50", replace(base, mr_weight=0.50, mom_weight=0.50)),
            ("no_hard_stop", replace(base, mr_hard_stop_pct=-1.0)),
            ("equal-weight mom", replace(base, mom_weighting="equal")),
            ("no cash proxy", replace(base, cash_proxy=None)),
            ("risk-assets-only mom", replace(base, mom_universe=[s for s in UNIVERSE if s not in ("SHY", "IEF", "LQD", "UUP")])),
            ("equities+gold mom", replace(base, mom_universe=[s for s in UNIVERSE if s not in ("SHY", "IEF", "LQD", "UUP", "TLT", "HYG", "DBC", "USO", "SLV")])),
            ("momentum only", replace(base, mr_weight=0.0, mom_weight=1.0)),
            ("mean-reversion only", replace(base, mr_weight=1.0, mom_weight=0.0, mr_max_positions=5)),
        ]
        print(f"{'variant':<22}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'MR n':>7}{'MR win':>8}")
        for name, prm in grid:
            r = run(hist, prm, args.start, args.end)
            print(f"{name:<22}{r['cagr']:>8.1%}{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}{r['mr_trades']:>7}{r['mr_win_rate']:>8.0%}")
        return 0

    if args.grid7:
        base = Params()
        agg = replace(base, core_leveraged=True, core_weight=0.5, core_candidates=("SPY", "QQQ"))
        grid = [
            ("balanced", base),
            ("aggressive", agg),
            ("bal + MR 25%", replace(base, mr_weight=0.25, mom_weight=0.75)),
            ("bal + vol 10%", replace(base, vol_target=0.10)),
            ("bal + vol 12%", replace(base, vol_target=0.12)),
            ("bal + def-mom", replace(base, defensive_mode="momentum")),
            ("bal + breadth .4", replace(base, breadth_min=0.4)),
            ("bal top8", replace(base, mom_top_n=8, mom_hysteresis=3)),
            ("bal top10", replace(base, mom_top_n=10, mom_hysteresis=4)),
            ("bal core 50% 1x", replace(base, core_weight=0.5)),
            ("core 1x 100%", replace(base, core_weight=1.0, core_candidates=("SPY", "QQQ"))),
            ("bal sma150", replace(base, trend_sma=150)),
            ("bal sma100", replace(base, trend_sma=100)),
        ]
        for start, label in ((args.start, "from " + args.start), ("2017-01-01", "OOS 2017+")):
            print(f"--- {label} ---")
            print(f"{'variant':<20}{'CAGR':>7}{'MaxDD':>7}{'LoseMo':>8}{'Lose12m':>8}{'Worst12m':>9}{'LoseYr':>7}{'UndrwtrMo':>10}")
            for name, prm in grid:
                r = run(hist, prm, start, args.end)
                print(f"{name:<20}{r['cagr']:>7.1%}{r['max_drawdown']:>7.0%}{r['losing_months']:>8.0%}{r['losing_12m']:>8.0%}{r['worst_12m']:>9.1%}{r['losing_years']:>7.0%}{r['longest_underwater_days']/21:>10.0f}")
        return 0

    if args.grid6:
        base = Params()
        us = ("SPY", "QQQ")
        grid = [("balanced (current)", base)]
        for cw in (0.3, 0.5, 0.7, 1.0):
            grid.append((f"2x core {cw:.0%} auto SPY/QQQ", replace(base, core_leveraged=True, core_weight=cw, core_candidates=us)))
        grid.append(("2x core 50% QQQ only", replace(base, core_leveraged=True, core_weight=0.5, core_symbol="QQQ")))
        grid.append(("1x core 100% auto (control)", replace(base, core_weight=1.0, core_candidates=us)))
        for start, label in (("2008-01-01", "2008+ (includes GFC)"), ("2015-01-01", "2015+"), ("2017-01-01", "OOS 2017+")):
            print(f"--- {label} ---")
            print(f"{'variant':<30}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'Calmar':>8}{'$1k->':>10}{'SPY':>8}")
            for name, prm in grid:
                r = run(hist, prm, start, args.end)
                print(f"{name:<30}{r['cagr']:>8.1%}{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}{r['calmar']:>8.2f}{r['end_equity']:>10,.0f}{r['spy']['cagr']:>8.1%}")
        return 0

    if args.grid5:
        base = Params()
        grid = [
            ("defaults", base),
            ("2 tranches", replace(base, mom_tranches=2)),
            ("5 tranches (daily stagger)", replace(base, mom_tranches=5)),
            ("core auto SPY/QQQ", replace(base, core_symbol="auto", core_candidates=("SPY", "QQQ"))),
            ("core auto SPY/QQQ/EFA", replace(base, core_symbol="auto")),
            ("core auto SPY/QQQ/EFA/EEM", replace(base, core_symbol="auto", core_candidates=("SPY", "QQQ", "EFA", "EEM"))),
            ("core auto SPY/EFA (GEM)", replace(base, core_symbol="auto", core_candidates=("SPY", "EFA"))),
            ("2 tranches + auto SPY/QQQ/EFA", replace(base, mom_tranches=2, core_symbol="auto")),
        ]
        for start, label in ((args.start, "from " + args.start), ("2015-01-01", "from 2015"), ("2017-01-01", "OOS 2017+")):
            print(f"--- {label} ---")
            print(f"{'variant':<32}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'Calmar':>8}{'Turn/yr':>9}")
            for name, prm in grid:
                r = run(hist, prm, start, args.end)
                print(f"{name:<32}{r['cagr']:>8.1%}{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}{r['calmar']:>8.2f}{r['annual_turnover']:>9.1f}")
        # timing-luck dispersion with tranches
        for name, prm in (("defaults", base), ("2 tranches", replace(base, mom_tranches=2)), ("5 tranches", replace(base, mom_tranches=5))):
            sh = [run(hist, prm, s)["sharpe"] for s in ("2008-01-02", "2008-01-03", "2008-01-04", "2008-01-07", "2008-01-08")]
            print(f"timing luck {name:<12}: Sharpe {min(sh):.2f} - {max(sh):.2f} (spread {max(sh)-min(sh):.2f})")
        return 0

    if args.grid4:
        base = Params()
        c6 = replace(base, mom_top_n=6, mom_rebalance_days=10)
        grid = [
            ("top5 5d (old default)", base),
            ("top6 10d (walk-fwd pick)", c6),
            ("top6 10d + cc.40", replace(c6, cluster_cap=0.40)),
            ("top6 10d + cc.50", replace(c6, cluster_cap=0.50)),
            ("top6 10d + cc.40 + b.40", replace(c6, cluster_cap=0.40, breadth_min=0.4)),
            ("top6 5d + cc.40", replace(c6, mom_rebalance_days=5, cluster_cap=0.40)),
            ("top5 5d + cc.40", replace(base, cluster_cap=0.40)),
            ("top6 10d cc.40 core SPY .3", replace(c6, cluster_cap=0.40, core_weight=0.3)),
            ("top6 10d cc.40 core SPY .5", replace(c6, cluster_cap=0.40, core_weight=0.5)),
            ("top6 10d cc.40 core QQQ .3", replace(c6, cluster_cap=0.40, core_weight=0.3, core_symbol="QQQ")),
            ("core SPY 1.0 (Faber timing)", replace(base, core_weight=1.0, mom_weight=0.0)),
        ]
        for start, label in ((args.start, "from " + args.start), ("2015-01-01", "from 2015"), ("2017-01-01", "OOS 2017+")):
            print(f"--- {label} ---")
            print(f"{'variant':<30}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'Calmar':>8}{'SPY CAGR':>10}")
            for name, prm in grid:
                r = run(hist, prm, start, args.end)
                print(f"{name:<30}{r['cagr']:>8.1%}{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}{r['calmar']:>8.2f}{r['spy']['cagr']:>10.1%}")
        return 0

    if args.grid3:
        base = Params()
        grid = [
            ("base (fixed BIL)", replace(base, defensive_mode="fixed")),
            ("defensive momentum", base),
            ("def-mom top2", replace(base, defensive_top_n=2)),
            ("breadth 0.3", replace(base, breadth_min=0.3)),
            ("breadth 0.4", replace(base, breadth_min=0.4)),
            ("breadth 0.5", replace(base, breadth_min=0.5)),
            ("cluster cap 0.40", replace(base, cluster_cap=0.40)),
            ("cluster cap 0.50", replace(base, cluster_cap=0.50)),
            ("vol target 10%", replace(base, vol_target=0.10)),
            ("vol target 12%", replace(base, vol_target=0.12)),
            ("vol target 15%", replace(base, vol_target=0.15)),
            ("daily+hyst2", replace(base, mom_rebalance_days=1)),
            ("daily+hyst3", replace(base, mom_rebalance_days=1, mom_hysteresis=3)),
            ("combo: cc.4 vt12", replace(base, cluster_cap=0.40, vol_target=0.12)),
            ("combo: cc.4 vt12 b.4", replace(base, cluster_cap=0.40, vol_target=0.12, breadth_min=0.4)),
            ("combo: cc.4 vt12 daily", replace(base, cluster_cap=0.40, vol_target=0.12, mom_rebalance_days=1)),
            ("combo: cc.5 vt15 daily", replace(base, cluster_cap=0.50, vol_target=0.15, mom_rebalance_days=1)),
        ]
        print(f"{'variant':<26}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'Calmar':>8}{'Vol':>7}{'Turn/yr':>9}")
        for name, prm in grid:
            r = run(hist, prm, args.start, args.end)
            print(f"{name:<26}{r['cagr']:>8.1%}{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}{r['calmar']:>8.2f}{r['vol']:>7.1%}{r['annual_turnover']:>9.1f}")
        return 0

    if args.grid2:
        base = Params()
        risk = [s for s in UNIVERSE if s not in ("SHY", "IEF", "LQD", "UUP")]
        broad = ["SPY", "QQQ", "IWM", "DIA", "MDY"]
        grid = [
            ("baseline", base),
            ("mom-only", replace(base, mr_weight=0.0, mom_weight=1.0)),
            ("mom-only equal", replace(base, mr_weight=0.0, mom_weight=1.0, mom_weighting="equal")),
            ("mom-only top4", replace(base, mr_weight=0.0, mom_weight=1.0, mom_top_n=4)),
            ("mom-only top4 equal", replace(base, mr_weight=0.0, mom_weight=1.0, mom_top_n=4, mom_weighting="equal")),
            ("mom-only top6", replace(base, mr_weight=0.0, mom_weight=1.0, mom_top_n=6)),
            ("mom-only risk univ", replace(base, mr_weight=0.0, mom_weight=1.0, mom_universe=risk)),
            ("mom-only lb 3/6/12", replace(base, mr_weight=0.0, mom_weight=1.0, mom_lookbacks=(63, 126, 252))),
            ("mom-only lb 1/3/6", replace(base, mr_weight=0.0, mom_weight=1.0, mom_lookbacks=(21, 63, 126))),
            ("mom-only hyst=0", replace(base, mr_weight=0.0, mom_weight=1.0, mom_hysteresis=0)),
            ("mom-only hyst=4", replace(base, mr_weight=0.0, mom_weight=1.0, mom_hysteresis=4)),
            ("mom-only reb=10d", replace(base, mr_weight=0.0, mom_weight=1.0, mom_rebalance_days=10)),
            ("mom .8 + MR .2 broad", replace(base, mr_weight=0.2, mom_weight=0.8, mr_max_positions=2)),
            ("mom .75 + MR .25", replace(base, mr_weight=0.25, mom_weight=0.75)),
            ("mom .75 + MR .25 rsi5", replace(base, mr_weight=0.25, mom_weight=0.75, mr_rsi_entry=5)),
        ]
        print(f"{'variant':<24}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'Calmar':>8}{'End$':>9}")
        for name, prm in grid:
            r = run(hist, prm, args.start, args.end)
            print(f"{name:<24}{r['cagr']:>8.1%}{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}{r['calmar']:>8.2f}{r['end_equity']:>9,.0f}")
        return 0

    r = run(hist, Params(), args.start, args.end, verbose=args.verbose)
    report = fmt_report(r, f"Backtest {args.start} -> {r['end']}")
    print(report)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write(report + "\n\n_Assumptions: fills at the close, "
                f"{SLIPPAGE_BPS:.0f} bps slippage per side, zero commissions, cash earns 0%, dividends reinvested "
                "(adjusted closes). Past performance is not a promise of future results._\n")
    if args.curve:
        with open(args.curve, "w") as f:
            f.write("date,equity\n")
            for d, e in r["curve"]:
                f.write(f"{d},{e:.2f}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
