"""Apply the news risk verdict to target weights (pure), and score it afterwards.

The overlay can ONLY move weight from risk assets into T-bills. It never adds a symbol,
never increases a weight, and does nothing unless the verdict is dated today.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

SAFE = {"BIL", "SHY", "IEF", "TLT", "GLD"}   # not scaled down by market-risk levels
CASH = "BIL"
DEFAULT_SCALE = {2: 0.75, 3: 0.50}          # market_risk level -> risk-asset exposure multiplier


def apply(weights: Dict[str, float], verdict: Optional[dict], today: str,
          scale: Optional[Dict[int, float]] = None, enabled: bool = True) -> Tuple[Dict[str, float], List[str]]:
    if not enabled or not verdict or verdict.get("date") != today:
        return dict(weights), []
    scale = {int(k): float(v) for k, v in (scale or DEFAULT_SCALE).items()}
    out = dict(weights)
    actions: List[str] = []
    level = int(verdict.get("market_risk") or 0)
    mult = min(1.0, max(0.0, scale.get(level, 1.0)))
    if mult < 1.0:
        moved = 0.0
        for s in list(out):
            if s not in SAFE:
                cut = out[s] * (1.0 - mult)
                out[s] -= cut
                moved += cut
        if moved > 1e-9:
            out[CASH] = out.get(CASH, 0.0) + moved
            actions.append(f"market risk {level}: risk exposure x{mult:.2f} ({moved:.0%} -> {CASH}) -- {verdict.get('market_reason', '')}")
    for v in verdict.get("vetoes") or []:
        s = v.get("symbol")
        if s in out and s != CASH and out[s] > 0:
            w = out.pop(s)
            out[CASH] = out.get(CASH, 0.0) + w
            actions.append(f"veto {s}: {w:.0%} -> {CASH} -- {v.get('reason', '')}")
    out = {s: w for s, w in out.items() if w > 1e-9}
    assert sum(out.values()) <= sum(weights.values()) + 1e-6
    return out, actions


def score_previous(log: List[dict], prices: Dict[str, float]) -> Optional[dict]:
    """Fill in the effect of the most recent unscored override using today's prices.
    effect = sum over symbols of (final - raw weight) * return since the override.
    Positive = the news layer saved money; negative = it cost money."""
    for e in reversed(log):
        if e.get("effect") is not None:
            return None
        diff = {s: e["final"].get(s, 0.0) - e["raw"].get(s, 0.0) for s in set(e["raw"]) | set(e["final"])}
        eff = 0.0
        for s, d in diff.items():
            p0, p1 = e["prices"].get(s), prices.get(s)
            if abs(d) > 1e-9 and p0 and p1:
                eff += d * (p1 / p0 - 1.0)
        e["effect"] = eff
        e["effect_dollars"] = round(eff * float(e.get("capital", 0.0)), 2)
        return e
    return None


def summary(log: List[dict]) -> dict:
    scored = [e for e in log if e.get("effect") is not None]
    return {
        "override_days": len(log), "scored": len(scored),
        "helped": sum(1 for e in scored if e["effect"] > 0), "hurt": sum(1 for e in scored if e["effect"] < 0),
        "net_dollars": round(sum(e.get("effect_dollars", 0.0) for e in scored), 2),
        "net_pct_of_capital": sum(e["effect"] for e in scored),
    }
