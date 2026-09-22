"""Systematic strategy: pure functions, no I/O, no broker.

Two sleeves on a fixed universe of liquid, commission-free ETFs (tight spreads,
no earnings gaps, fractional-share eligible):

  A) MOMENTUM ROTATION (default 100% of capital, rebalanced weekly)
     Rank the universe by average 3/6/12-month total return. Hold the top N
     that are ALSO in an uptrend (price > 200-day SMA) with positive momentum
     (absolute-momentum filter). Slots with no eligible candidate sit in cash,
     so exposure falls automatically in bear markets. Weights are inverse-vol
     tilted so a calm bond ETF and a wild semiconductor ETF contribute similar
     risk. A held name keeps its slot while it stays inside the top N+2
     (hysteresis) to cut churn.

  B) SHORT-TERM MEAN REVERSION (OPTIONAL, off by default; evaluated daily)
     Buy an equity ETF that is in an uptrend (price > 200-day SMA) but
     short-term washed out (2-period RSI <= 10). Exit when it snaps back
     (close > 5-day SMA or RSI(2) > 65), after a time stop, or on a hard
     catastrophe stop. Classic "buy the dip in an uptrend".

Everything here takes plain lists/dicts so it runs identically inside the
backtester and the live executor. Daily bars in, target weights out.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import date as _date
from typing import Dict, List, Optional, Sequence

# --------------------------------------------------------------------------- #
# Universe                                                                    #
# --------------------------------------------------------------------------- #
# Liquid ETFs only. Adding single stocks re-introduces earnings gaps and wide
# spreads: the exact failure mode of the old small-cap-news strategy.
UNIVERSE: List[str] = [
    # US broad
    "SPY", "QQQ", "IWM", "DIA", "MDY",
    # US sectors / industries
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
    "SMH", "XBI", "VNQ",
    # International
    "EFA", "EEM", "VGK", "EWJ", "FXI",
    # Bonds
    "TLT", "IEF", "LQD", "HYG", "SHY",
    # Commodities / currency
    "GLD", "SLV", "DBC", "USO", "UUP",
]

# Mean reversion only on equity-like ETFs; bonds/currency don't "snap back" the same way.
MR_UNIVERSE: List[str] = [
    "SPY", "QQQ", "IWM", "DIA", "MDY",
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
    "SMH", "XBI", "VNQ", "EFA", "EEM", "VGK", "EWJ", "FXI",
]


@dataclass
class Params:
    # Sleeve A: momentum rotation
    mom_weight: float = 1.00          # fraction of capital for the momentum sleeve
    mom_top_n: int = 5                # how many names to hold
    mom_hysteresis: int = 2           # keep a holding while it ranks within top_n + this
    mom_lookbacks: Sequence[int] = (63, 126, 252)  # trading days: 3m/6m/12m (the most recent
                                                   # month is excluded on purpose: 1-month returns
                                                   # mean-revert; see backtest grid)
    trend_sma: int = 200              # uptrend filter
    vol_lookback: int = 63            # for inverse-vol tilt
    mom_rebalance_days: int = 5       # rebalance every N trading days (weekly)
    mom_weighting: str = "inverse_vol"  # or "equal"
    mom_universe: Optional[Sequence[str]] = None  # None = strategy.UNIVERSE
    cash_proxy: Optional[str] = "BIL"  # park idle capital in T-bills (None = raw cash)
    # Sleeve B: mean reversion
    mr_weight: float = 0.00           # OFF by default: the backtest shows it dilutes the
                                      # momentum sleeve in every window tested. Kept as an
                                      # optional, tested sleeve for experimentation.
    mr_max_positions: int = 4
    mr_rsi_period: int = 2
    mr_rsi_entry: float = 10.0
    mr_rsi_exit: float = 65.0
    mr_exit_sma: int = 5
    mr_time_stop_days: int = 10
    mr_hard_stop_pct: float = -0.10   # catastrophe stop on a single MR position
    # Portfolio-level
    max_position_weight: float = 0.35 # cap on any one symbol across sleeves
    min_history: int = 260            # bars needed before a symbol is tradeable


@dataclass
class MRPosition:
    symbol: str
    entry_date: str
    entry_price: float
    days_held: int = 0


@dataclass
class State:
    """Carried between runs (persisted by the executor, kept in-memory by the backtester)."""
    mom_holdings: List[str] = field(default_factory=list)
    mom_days_since_rebalance: int = 9999  # force a rebalance on first run
    mr_positions: Dict[str, MRPosition] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "State":
        if not d:
            return cls()
        s = cls()
        s.mom_holdings = list(d.get("mom_holdings", []))
        s.mom_days_since_rebalance = int(d.get("mom_days_since_rebalance", 9999))
        for sym, p in (d.get("mr_positions") or {}).items():
            s.mr_positions[sym] = MRPosition(
                symbol=sym,
                entry_date=str(p.get("entry_date", "")),
                entry_price=float(p.get("entry_price", 0.0)),
                days_held=int(p.get("days_held", 0)),
            )
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

    @property
    def uptrend(self) -> bool:
        return self.sma_trend is not None and self.close > self.sma_trend


# --------------------------------------------------------------------------- #
# Indicator helpers (closes are oldest -> newest)                             #
# --------------------------------------------------------------------------- #
def sma(closes: Sequence[float], n: int) -> Optional[float]:
    if len(closes) < n or n <= 0:
        return None
    return sum(closes[-n:]) / n


def rsi(closes: Sequence[float], n: int) -> Optional[float]:
    """Wilder RSI over the last n changes (needs n+1 closes; uses Wilder smoothing over
    the whole series for stability, like every charting package)."""
    if len(closes) < n + 1:
        return None
    gains = 0.0
    losses = 0.0
    # seed with simple average of first n changes
    for i in range(1, n + 1):
        ch = closes[i] - closes[i - 1]
        if ch > 0:
            gains += ch
        else:
            losses -= ch
    avg_gain = gains / n
    avg_loss = losses / n
    for i in range(n + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g = ch if ch > 0 else 0.0
        l = -ch if ch < 0 else 0.0
        avg_gain = (avg_gain * (n - 1) + g) / n
        avg_loss = (avg_loss * (n - 1) + l) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


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


def annual_vol(closes: Sequence[float], n: int) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    window = closes[-(n + 1):]
    lr = [math.log(window[i] / window[i - 1]) for i in range(1, len(window)) if window[i - 1] > 0 and window[i] > 0]
    if len(lr) < 2:
        return None
    m = sum(lr) / len(lr)
    var = sum((x - m) ** 2 for x in lr) / (len(lr) - 1)
    return math.sqrt(var) * math.sqrt(252)


def compute_signals(closes: Sequence[float], p: Params) -> Signals:
    return Signals(
        close=closes[-1],
        sma_trend=sma(closes, p.trend_sma),
        sma_exit=sma(closes, p.mr_exit_sma),
        rsi=rsi(closes[-(p.mr_rsi_period * 60 + 1):] if len(closes) > p.mr_rsi_period * 60 else closes, p.mr_rsi_period),
        mom_score=momentum_score(closes, p.mom_lookbacks),
        vol=annual_vol(closes, p.vol_lookback),
        n_bars=len(closes),
    )


# --------------------------------------------------------------------------- #
# Target construction                                                         #
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    weights: Dict[str, float]            # symbol -> target fraction of capital (sum <= 1)
    state: State                         # updated state to persist
    notes: List[str]                     # human-readable reasons
    mom_selected: List[str]
    mr_open: List[str]
    rebalanced_momentum: bool


def compute_targets(
    history: Optional[Dict[str, Sequence[float]]],
    state: State,
    p: Params = Params(),
    today: Optional[str] = None,
    signals: Optional[Dict[str, Signals]] = None,
) -> Decision:
    """history: symbol -> closes (oldest..newest, the LAST value is today's price).
    `signals` may be passed instead (the backtester precomputes them incrementally;
    same formulas, see tests). Returns target weights + the state to carry forward.
    Pure: no side effects."""
    notes: List[str] = []
    sig: Dict[str, Signals] = {}
    if signals is not None:
        sig = {s: g for s, g in signals.items() if g.n_bars >= p.min_history}
    else:
        for sym, closes in (history or {}).items():
            if closes and len(closes) >= p.min_history:
                sig[sym] = compute_signals(closes, p)

    # ------------------------- Sleeve A: momentum rotation -------------------
    st = State.from_dict(state.to_dict())  # deep copy
    st.mom_days_since_rebalance += 1
    rebalance = st.mom_days_since_rebalance >= p.mom_rebalance_days

    mom_univ = set(p.mom_universe) if p.mom_universe else set(UNIVERSE)
    eligible = {
        s: sg for s, sg in sig.items()
        if s in mom_univ and sg.mom_score is not None and sg.mom_score > 0 and sg.uptrend and sg.vol
    }
    ranked = sorted(eligible, key=lambda s: eligible[s].mom_score, reverse=True)

    if rebalance:
        keep_zone = set(ranked[: p.mom_top_n + p.mom_hysteresis])
        selected = [s for s in st.mom_holdings if s in keep_zone]
        for s in ranked:
            if len(selected) >= p.mom_top_n:
                break
            if s not in selected:
                selected.append(s)
        dropped = [s for s in st.mom_holdings if s not in selected]
        added = [s for s in selected if s not in st.mom_holdings]
        if dropped or added:
            notes.append(f"momentum rebalance: +{added or '-'} -{dropped or '-'}")
        else:
            notes.append("momentum rebalance: no changes")
        st.mom_holdings = selected
        st.mom_days_since_rebalance = 0
    else:
        # Between rebalances only drop a holding that has broken its uptrend.
        still = [s for s in st.mom_holdings if s in sig and sig[s].uptrend]
        broke = [s for s in st.mom_holdings if s not in still]
        if broke:
            notes.append(f"momentum trend-break exit: {broke}")
        st.mom_holdings = still

    weights: Dict[str, float] = {}

    # ----------------------- Sleeve B: mean reversion ------------------------
    # (evaluated first so idle MR capital can be handed to the momentum sleeve)
    slot = (p.mr_weight / p.mr_max_positions) if p.mr_weight > 0 else 0.0
    mr_enabled = p.mr_weight > 0
    closed: List[str] = []
    for sym, pos in list(st.mr_positions.items()):
        sg = sig.get(sym)
        pos.days_held += 1
        if sg is None:
            closed.append(sym); notes.append(f"MR exit {sym}: no data"); continue
        ret = sg.close / pos.entry_price - 1.0
        reason = None
        if sg.sma_exit is not None and sg.close > sg.sma_exit:
            reason = f"close>SMA{p.mr_exit_sma}"
        elif sg.rsi is not None and sg.rsi > p.mr_rsi_exit:
            reason = f"RSI{p.mr_rsi_period}>{p.mr_rsi_exit:.0f}"
        elif pos.days_held >= p.mr_time_stop_days:
            reason = f"time stop {p.mr_time_stop_days}d"
        elif ret <= p.mr_hard_stop_pct:
            reason = f"hard stop {ret:+.1%}"
        if reason:
            closed.append(sym)
            notes.append(f"MR exit {sym} {ret:+.2%} ({reason})")
    for sym in closed:
        del st.mr_positions[sym]

    free = (p.mr_max_positions - len(st.mr_positions)) if mr_enabled else 0
    if not mr_enabled and st.mr_positions:
        notes.append(f"MR sleeve disabled: releasing {list(st.mr_positions)}")
        st.mr_positions.clear()
    if free > 0:
        cands = [
            s for s in MR_UNIVERSE
            if s in sig and s not in st.mr_positions
            and sig[s].uptrend and sig[s].rsi is not None and sig[s].rsi <= p.mr_rsi_entry
        ]
        cands.sort(key=lambda s: sig[s].rsi)  # most oversold first
        for s in cands[:free]:
            st.mr_positions[s] = MRPosition(symbol=s, entry_date=today or "", entry_price=sig[s].close, days_held=0)
            notes.append(f"MR entry {s} @ {sig[s].close:.2f} (RSI{p.mr_rsi_period}={sig[s].rsi:.1f})")
    for sym in st.mr_positions:
        weights[sym] = weights.get(sym, 0.0) + slot

    # ----------------------- Sleeve A weights ---------------------------------
    # Momentum gets its own budget PLUS whatever the MR sleeve is not using.
    mr_used = slot * len(st.mr_positions)
    mom_budget = max(0.0, 1.0 - mr_used) if p.mr_weight + p.mom_weight >= 0.999 else p.mom_weight + (p.mr_weight - mr_used)
    if st.mom_holdings:
        if p.mom_weighting == "equal":
            raw = {s: 1.0 for s in st.mom_holdings}
        else:
            raw = {s: 1.0 / max(sig[s].vol, 0.02) for s in st.mom_holdings}
        tot = sum(raw.values())
        sleeve_cap = mom_budget * len(st.mom_holdings) / p.mom_top_n
        for s, v in raw.items():
            weights[s] = weights.get(s, 0.0) + sleeve_cap * v / tot

    # ----------------------------- caps ----------------------------------------
    for s in list(weights):
        weights[s] = min(weights[s], p.max_position_weight)
    total = sum(weights.values())
    if total > 1.0:  # never leveraged
        weights = {s: w / total for s, w in weights.items()}
        total = 1.0
    # Idle capital -> T-bill ETF (earns the risk-free rate instead of 0%).
    if p.cash_proxy and p.cash_proxy in sig and total < 0.999:
        weights[p.cash_proxy] = weights.get(p.cash_proxy, 0.0) + (1.0 - total)

    return Decision(
        weights={s: round(w, 6) for s, w in weights.items() if w > 0},
        state=st,
        notes=notes,
        mom_selected=list(st.mom_holdings),
        mr_open=list(st.mr_positions),
        rebalanced_momentum=rebalance,
    )
