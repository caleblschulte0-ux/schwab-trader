"""Systematic strategy: pure functions, no I/O, no broker.

MOMENTUM ROTATION over a fixed universe of liquid, commission-free ETFs, with layered
risk controls. Daily bars in, target weights out. The same code runs inside the
backtester and the live executor.

  1. Score each ETF by the average of its 3/6/12-month total returns.
  2. Eligible = positive score AND price above its 200-day SMA (absolute momentum).
  3. Regime: if market breadth (% of the risk universe above its 200-day SMA) is below
     `breadth_min`, go fully defensive.
  4. Hold the top N eligible; a holding keeps its slot while it stays inside the top
     N + hysteresis. Weights inverse to volatility, capped per symbol and per cluster
     (so five oil-flavoured ETFs cannot become one bet).
  5. Unfilled slots -> the best DEFENSIVE asset by momentum (T-bills, treasuries, gold),
     floor = T-bills. In 2008 that meant long treasuries, not 0% cash.
  6. Portfolio volatility targeting: if the target book's realised vol exceeds
     `vol_target`, scale exposure down (never up: no leverage). The remainder sits in
     the defensive asset.

An optional short-term mean-reversion sleeve is kept (off by default).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

# --------------------------------------------------------------------------- #
# Universe                                                                    #
# --------------------------------------------------------------------------- #
UNIVERSE: List[str] = [
    "SPY", "QQQ", "IWM", "DIA", "MDY",                                             # US broad
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",  # US sectors
    "SMH", "XBI", "VNQ",                                                           # industries
    "EFA", "EEM", "VGK", "EWJ", "FXI",                                             # international
    "TLT", "IEF", "LQD", "HYG", "SHY",                                             # bonds
    "GLD", "SLV", "DBC", "USO", "UUP",                                             # commodities / FX
]

# Assets the strategy may hold when it is being defensive (chosen by momentum, floor BIL).
DEFENSIVE: List[str] = ["BIL", "SHY", "IEF", "TLT", "GLD"]

# Breadth is measured on the RISK part of the universe only.
RISK_UNIVERSE: List[str] = [s for s in UNIVERSE if s not in ("TLT", "IEF", "LQD", "SHY", "UUP")]

MR_UNIVERSE: List[str] = [
    "SPY", "QQQ", "IWM", "DIA", "MDY", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU",
    "XLB", "XLRE", "XLC", "SMH", "XBI", "VNQ", "EFA", "EEM", "VGK", "EWJ", "FXI",
]

# Leveraged (2x daily) versions of core candidates. Held ONLY by the core sleeve, ONLY while
# the UNDERLYING index is above its 200-day SMA (the trend filter reads the underlying).
LEVERAGED: Dict[str, str] = {"SPY": "SSO", "QQQ": "QLD"}

# Economic clusters for the per-cluster cap.
CLUSTERS: Dict[str, str] = {
    "SPY": "us_equity", "QQQ": "us_equity", "IWM": "us_equity", "DIA": "us_equity", "MDY": "us_equity",
    "XLK": "tech", "SMH": "tech", "XLC": "tech",
    "XLF": "cyclical", "XLI": "cyclical", "XLY": "cyclical", "XLB": "cyclical",
    "XLV": "defensive_eq", "XLP": "defensive_eq", "XLU": "defensive_eq", "XBI": "health",
    "XLRE": "real_estate", "VNQ": "real_estate",
    "EFA": "intl", "VGK": "intl", "EWJ": "intl", "EEM": "em", "FXI": "em",
    "TLT": "treasuries", "IEF": "treasuries", "SHY": "treasuries", "BIL": "treasuries",
    "LQD": "credit", "HYG": "credit",
    "GLD": "metals", "SLV": "metals", "DBC": "energy", "USO": "energy", "XLE": "energy", "UUP": "fx",
    "SSO": "core_lev", "QLD": "core_lev",
}


@dataclass
class Params:
    # Momentum sleeve
    mom_weight: float = 1.00
    mom_top_n: int = 8                               # 8 names: fewer losing months than 6 (grid7)
    mom_hysteresis: int = 3
    mom_lookbacks: Sequence[int] = (63, 126, 252)   # 3/6/12 months; the last month is excluded on
                                                     # purpose (1-month returns mean-revert)
    trend_sma: int = 150                             # 150d: smaller drawdowns than 200d (grid7)
    vol_lookback: int = 63
    mom_rebalance_days: int = 10                     # every 2 weeks (walk-forward pick); 1 = daily
    mom_weighting: str = "inverse_vol"               # or "equal"
    mom_universe: Optional[Sequence[str]] = None     # None = UNIVERSE
    mom_tranches: int = 5                            # split the sleeve into N staggered rebalance
                                                     # cycles to average out rebalance-timing luck
    # Optional core sleeve: fixed slice in `core_symbol` while it is above its 200-day SMA
    core_weight: float = 0.50                        # 0 = off. Trend-timed index core
    core_symbol: str = "auto"                        # "auto": strongest of core_candidates by momentum, or a ticker
    core_candidates: Sequence[str] = ("SPY", "QQQ", "EFA")
    core_leveraged: bool = False                     # hold the 2x ETF (LEVERAGED map) instead
    # Regime / defensive
    breadth_min: float = 0.0                         # 0 = off. e.g. 0.4 -> fully defensive when <40% of
                                                     # the risk universe is above its 200-day SMA
    defensive_mode: str = "fixed"                    # "fixed" (cash_proxy) or "momentum" (best of DEFENSIVE)
                                                     # -- backtest: momentum picks TLT into 2022, worse DD
    cash_proxy: Optional[str] = "BIL"                # floor / fixed defensive asset (None = raw cash)
    defensive_top_n: int = 1
    # Risk overlays
    vol_target: Optional[float] = None               # e.g. 0.12 -> scale exposure down above 12% vol
    max_position_weight: float = 0.35
    cluster_cap: float = 0.40                        # max 40% of capital per economic cluster (1.0 = off)
    # Optional mean-reversion sleeve (off by default)
    mr_weight: float = 0.00
    mr_max_positions: int = 4
    mr_rsi_period: int = 2
    mr_rsi_entry: float = 10.0
    mr_rsi_exit: float = 65.0
    mr_exit_sma: int = 5
    mr_time_stop_days: int = 10
    mr_hard_stop_pct: float = -0.10
    # General
    min_history: int = 260


@dataclass
class MRPosition:
    symbol: str
    entry_date: str
    entry_price: float
    days_held: int = 0


@dataclass
class Tranche:
    holdings: List[str] = field(default_factory=list)
    days_since_rebalance: int = 9999
    next_offset: int = 0   # after its FIRST rebalance a tranche restarts its clock here (stagger)


@dataclass
class State:
    mom_holdings: List[str] = field(default_factory=list)      # union of tranche holdings (reporting)
    mom_days_since_rebalance: int = 9999                      # tranche 0 (kept for compatibility)
    mr_positions: Dict[str, MRPosition] = field(default_factory=dict)
    tranches: List[Tranche] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "State":
        s = cls()
        if not d:
            return s
        s.mom_holdings = list(d.get("mom_holdings", []))
        s.mom_days_since_rebalance = int(d.get("mom_days_since_rebalance", 9999))
        for t in d.get("tranches") or []:
            s.tranches.append(Tranche(list(t.get("holdings", [])), int(t.get("days_since_rebalance", 9999)),
                                      int(t.get("next_offset", 0))))
        for sym, p in (d.get("mr_positions") or {}).items():
            s.mr_positions[sym] = MRPosition(sym, str(p.get("entry_date", "")), float(p.get("entry_price", 0.0)),
                                             int(p.get("days_held", 0)))
        return s


@dataclass
class Signals:
    close: float
    sma_trend: Optional[float]
    sma_exit: Optional[float]
    rsi: Optional[float]
    mom_score: Optional[float]
    vol: Optional[float]
    n_bars: int
    rets: Sequence[float] = ()   # last `vol_lookback` daily returns (for portfolio vol)

    @property
    def uptrend(self) -> bool:
        return self.sma_trend is not None and self.close > self.sma_trend


# --------------------------------------------------------------------------- #
# Indicators                                                                  #
# --------------------------------------------------------------------------- #
def sma(closes: Sequence[float], n: int) -> Optional[float]:
    if n <= 0 or len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def rsi(closes: Sequence[float], n: int) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(ch, 0.0)) / n
        al = (al * (n - 1) + max(-ch, 0.0)) / n
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def momentum_score(closes: Sequence[float], lookbacks: Sequence[int]) -> Optional[float]:
    if len(closes) <= max(lookbacks):
        return None
    last = closes[-1]
    rets = []
    for lb in lookbacks:
        base = closes[-1 - lb]
        if base <= 0:
            return None
        rets.append(last / base - 1.0)
    return sum(rets) / len(rets)


def daily_returns(closes: Sequence[float], n: int) -> List[float]:
    w = closes[-(n + 1):]
    return [w[i] / w[i - 1] - 1.0 for i in range(1, len(w)) if w[i - 1] > 0]


def annual_vol(closes: Sequence[float], n: int) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    w = closes[-(n + 1):]
    lr = [math.log(w[i] / w[i - 1]) for i in range(1, len(w)) if w[i - 1] > 0 and w[i] > 0]
    if len(lr) < 2:
        return None
    m = sum(lr) / len(lr)
    return math.sqrt(sum((x - m) ** 2 for x in lr) / (len(lr) - 1)) * math.sqrt(252)


def compute_signals(closes: Sequence[float], p: Params) -> Signals:
    tail = closes[-(p.mr_rsi_period * 60 + 1):] if len(closes) > p.mr_rsi_period * 60 else closes
    return Signals(
        close=closes[-1],
        sma_trend=sma(closes, p.trend_sma),
        sma_exit=sma(closes, p.mr_exit_sma),
        rsi=rsi(tail, p.mr_rsi_period),
        mom_score=momentum_score(closes, p.mom_lookbacks),
        vol=annual_vol(closes, p.vol_lookback),
        n_bars=len(closes),
        rets=daily_returns(closes, p.vol_lookback) if len(closes) > p.vol_lookback else (),
    )


def portfolio_vol(weights: Dict[str, float], sig: Dict[str, Signals]) -> Optional[float]:
    """Annualised vol of the weighted book from its constituents' recent daily returns."""
    syms = [s for s, w in weights.items() if w > 0 and s in sig and sig[s].rets]
    if not syms:
        return None
    n = min(len(sig[s].rets) for s in syms)
    if n < 20:
        return None
    series = [sum(weights[s] * sig[s].rets[-n:][i] for s in syms) for i in range(n)]
    m = sum(series) / n
    var = sum((x - m) ** 2 for x in series) / (n - 1)
    return math.sqrt(var) * math.sqrt(252)


# --------------------------------------------------------------------------- #
# Target construction                                                         #
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    weights: Dict[str, float]
    state: State
    notes: List[str]
    mom_selected: List[str]
    mr_open: List[str]
    rebalanced_momentum: bool
    regime: Dict[str, object] = field(default_factory=dict)


def _apply_caps(weights: Dict[str, float], p: Params, exempt: Optional[set] = None) -> float:
    """Per-symbol and per-cluster caps. Returns the freed weight (to send to defensive).
    `exempt`: the core sleeve's holding (sized deliberately by core_weight)."""
    freed = 0.0
    exempt = exempt or set()
    for s in list(weights):
        if s in exempt:
            continue
        if weights[s] > max(p.max_position_weight, 0.0):
            freed += weights[s] - p.max_position_weight
            weights[s] = p.max_position_weight
    if p.cluster_cap < 1.0:
        totals: Dict[str, float] = {}
        for s, w in weights.items():
            if s in exempt:
                continue
            totals[CLUSTERS.get(s, s)] = totals.get(CLUSTERS.get(s, s), 0.0) + w
        for c, tot in totals.items():
            if tot > p.cluster_cap + 1e-12:
                scale = p.cluster_cap / tot
                for s in weights:
                    if CLUSTERS.get(s, s) == c and s not in exempt:
                        freed += weights[s] * (1 - scale)
                        weights[s] *= scale
    return freed


def _defensive_picks(sig: Dict[str, Signals], p: Params) -> List[str]:
    if p.defensive_mode != "momentum":
        return [p.cash_proxy] if p.cash_proxy else []
    cands = [s for s in DEFENSIVE if s in sig and sig[s].mom_score is not None]
    cands.sort(key=lambda s: sig[s].mom_score, reverse=True)
    picks = [s for s in cands if sig[s].mom_score > 0 and sig[s].uptrend][: p.defensive_top_n]
    if not picks:
        picks = [p.cash_proxy] if p.cash_proxy and p.cash_proxy in sig else []
    return picks


def compute_targets(
    history: Optional[Dict[str, Sequence[float]]],
    state: State,
    p: Params = Params(),
    today: Optional[str] = None,
    signals: Optional[Dict[str, Signals]] = None,
) -> Decision:
    """history: symbol -> closes (oldest..newest; the LAST value is today's price)."""
    notes: List[str] = []
    if signals is not None:
        sig = {s: g for s, g in signals.items() if g.n_bars >= p.min_history}
    else:
        sig = {s: compute_signals(c, p) for s, c in (history or {}).items() if c and len(c) >= p.min_history}

    st = State.from_dict(state.to_dict())
    st.mom_days_since_rebalance += 1
    rebalance = st.mom_days_since_rebalance >= p.mom_rebalance_days

    # ------------------------------------------------ regime / breadth
    risk = [s for s in RISK_UNIVERSE if s in sig]
    breadth = (sum(1 for s in risk if sig[s].uptrend) / len(risk)) if risk else 0.0
    risk_off = p.breadth_min > 0 and breadth < p.breadth_min
    regime = {"breadth": round(breadth, 3), "risk_off": risk_off}

    # ------------------------------------------------ momentum selection
    mom_univ = set(p.mom_universe) if p.mom_universe else set(UNIVERSE)
    eligible = {s: g for s, g in sig.items()
                if s in mom_univ and g.mom_score is not None and g.mom_score > 0 and g.uptrend and g.vol}
    ranked = sorted(eligible, key=lambda s: eligible[s].mom_score, reverse=True)

    # tranches: initialise (staggered) or migrate a single-tranche state
    n_tr = max(1, int(p.mom_tranches))
    if len(st.tranches) != n_tr:
        # Fresh start or tranche-count change: every tranche inherits the current holdings and
        # rebalances NOW (full investment on day one); after that first rebalance tranche k
        # restarts its clock at k*step so the cycles are staggered from then on.
        step = max(1, p.mom_rebalance_days // n_tr)
        st.tranches = [Tranche(list(st.mom_holdings), 9999, k * step) for k in range(n_tr)]
        st.mom_days_since_rebalance = 9999
    rebalance = False
    for k, tr in enumerate(st.tranches):
        if k > 0:
            tr.days_since_rebalance += 1
        else:
            tr.days_since_rebalance = st.mom_days_since_rebalance
        tr_reb = tr.days_since_rebalance >= p.mom_rebalance_days
        rebalance = rebalance or tr_reb
        tag = f"tranche {k + 1}/{n_tr} " if n_tr > 1 else ""
        if risk_off:
            if tr.holdings:
                notes.append(f"{tag}regime risk-off (breadth {breadth:.0%} < {p.breadth_min:.0%}): exiting {tr.holdings}")
            tr.holdings = []
            if tr_reb:
                tr.days_since_rebalance = tr.next_offset
                tr.next_offset = 0
        elif tr_reb:
            keep_zone = set(ranked[: p.mom_top_n + p.mom_hysteresis])
            selected = [s for s in tr.holdings if s in keep_zone]
            for s in ranked:
                if len(selected) >= p.mom_top_n:
                    break
                if s not in selected:
                    selected.append(s)
            added = [s for s in selected if s not in tr.holdings]
            dropped = [s for s in tr.holdings if s not in selected]
            if added or dropped:
                notes.append(f"{tag}momentum rebalance: +{added or '-'} -{dropped or '-'}")
            tr.holdings = selected
            tr.days_since_rebalance = tr.next_offset
            tr.next_offset = 0
        else:
            still = [s for s in tr.holdings if s in sig and sig[s].uptrend]
            broke = [s for s in tr.holdings if s not in still]
            if broke:
                notes.append(f"{tag}momentum trend-break exit: {broke}")
            tr.holdings = still
    st.mom_days_since_rebalance = st.tranches[0].days_since_rebalance
    st.mom_holdings = sorted({s for tr in st.tranches for s in tr.holdings})

    weights: Dict[str, float] = {}

    # ------------------------------------------------ optional mean-reversion sleeve
    mr_enabled = p.mr_weight > 0
    slot = (p.mr_weight / p.mr_max_positions) if mr_enabled else 0.0
    for sym, pos in list(st.mr_positions.items()):
        g = sig.get(sym)
        pos.days_held += 1
        reason = None
        if not mr_enabled:
            reason = "sleeve disabled"
        elif g is None:
            reason = "no data"
        else:
            ret = g.close / pos.entry_price - 1.0
            if g.sma_exit is not None and g.close > g.sma_exit:
                reason = f"close>SMA{p.mr_exit_sma}"
            elif g.rsi is not None and g.rsi > p.mr_rsi_exit:
                reason = f"RSI{p.mr_rsi_period}>{p.mr_rsi_exit:.0f}"
            elif pos.days_held >= p.mr_time_stop_days:
                reason = f"time stop {p.mr_time_stop_days}d"
            elif ret <= p.mr_hard_stop_pct:
                reason = f"hard stop {ret:+.1%}"
            if reason:
                reason = f"{ret:+.2%} ({reason})"
        if reason:
            notes.append(f"MR exit {sym} {reason}")
            del st.mr_positions[sym]
    free = (p.mr_max_positions - len(st.mr_positions)) if mr_enabled and not risk_off else 0
    if free > 0:
        cands = [s for s in MR_UNIVERSE if s in sig and s not in st.mr_positions
                 and sig[s].uptrend and sig[s].rsi is not None and sig[s].rsi <= p.mr_rsi_entry]
        cands.sort(key=lambda s: sig[s].rsi)
        for s in cands[:free]:
            st.mr_positions[s] = MRPosition(s, today or "", sig[s].close, 0)
            notes.append(f"MR entry {s} @ {sig[s].close:.2f} (RSI{p.mr_rsi_period}={sig[s].rsi:.1f})")
    for sym in st.mr_positions:
        weights[sym] = weights.get(sym, 0.0) + slot

    # ------------------------------------------------ core sleeve
    core_used = 0.0
    core_pick: Optional[str] = None
    if p.core_weight > 0 and not risk_off:
        if p.core_symbol == "auto":
            cands = [s for s in p.core_candidates if s in sig and sig[s].mom_score is not None
                     and sig[s].mom_score > 0 and sig[s].uptrend]
            core_pick = max(cands, key=lambda s: sig[s].mom_score) if cands else None
        elif p.core_symbol in sig and sig[p.core_symbol].uptrend:
            core_pick = p.core_symbol
        if core_pick:
            hold = LEVERAGED.get(core_pick, core_pick) if p.core_leveraged else core_pick
            if hold not in sig:          # no data for the 2x fund -> fall back to the index
                hold = core_pick
            weights[hold] = weights.get(hold, 0.0) + p.core_weight
            core_used = p.core_weight
            core_pick = hold
    regime["core"] = core_pick
    # ------------------------------------------------ momentum weights
    mr_used = slot * len(st.mr_positions)
    mom_budget = max(0.0, 1.0 - mr_used - p.core_weight) if p.mr_weight + p.mom_weight >= 0.999 else p.mom_weight + (p.mr_weight - mr_used) - p.core_weight
    mom_budget = max(0.0, mom_budget)
    for tr in st.tranches:
        if not tr.holdings:
            continue
        raw = {s: (1.0 if p.mom_weighting == "equal" else 1.0 / max(sig[s].vol, 0.02)) for s in tr.holdings}
        tot = sum(raw.values())
        sleeve_cap = (mom_budget / n_tr) * len(tr.holdings) / p.mom_top_n
        for s, v in raw.items():
            weights[s] = weights.get(s, 0.0) + sleeve_cap * v / tot

    # ------------------------------------------------ caps, vol targeting, defensive fill
    # Caps apply to the rotation only: take the core slice out, cap, put it back.
    if core_pick and core_used > 0:
        weights[core_pick] -= core_used
        if weights[core_pick] <= 1e-12:
            del weights[core_pick]
    freed = _apply_caps(weights, p)
    if core_pick and core_used > 0:
        weights[core_pick] = weights.get(core_pick, 0.0) + core_used
    total = sum(weights.values())
    if total > 1.0:
        weights = {s: w / total for s, w in weights.items()}
        total = 1.0
    scale = 1.0
    if p.vol_target and weights:
        pv = portfolio_vol(weights, sig)
        if pv and pv > p.vol_target:
            scale = p.vol_target / pv
            weights = {s: w * scale for s, w in weights.items()}
            total = sum(weights.values())
            notes.append(f"vol targeting: book vol {pv:.0%} > {p.vol_target:.0%}, exposure x{scale:.2f}")
        regime["book_vol"] = round(pv, 3) if pv else None
    regime["exposure"] = round(total, 3)

    idle = max(0.0, 1.0 - total)
    if idle > 1e-6:
        picks = _defensive_picks(sig, p)
        if picks:
            each = idle / len(picks)
            for s in picks:
                weights[s] = weights.get(s, 0.0) + each
            regime["defensive"] = picks
            if idle > 0.05:
                notes.append(f"defensive {idle:.0%} -> {picks}")

    return Decision(
        weights={s: math.floor(w * 1e6) / 1e6 for s, w in weights.items() if w > 1e-6},  # round DOWN: sum never > 1
        state=st,
        notes=notes,
        mom_selected=list(st.mom_holdings),
        mr_open=list(st.mr_positions),
        rebalanced_momentum=rebalance,
        regime=regime,
    )
