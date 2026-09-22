"""config.json -> strategy.Params + executor settings. Env vars override executor settings."""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Any, Dict, Tuple

from strategy import Params

CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.json")
_EXEC_DEFAULTS: Dict[str, Any] = {
    "max_capital": None, "max_drawdown_halt": 0.30, "trade_window_min": 60.0,
    "min_trade_dollars": 5.0, "sim_start_cash": 1000.0,
    "live_min_paper_runs": 20.0,   # clean Alpaca PAPER runs required before LIVE is allowed
}


# If config.json's executor block merely restates the default for these, a preset's own value wins.
_PRESET_OVERRIDABLE = {"max_drawdown_halt"}


def load_config(path: str = CONFIG_FILE) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def build_params(cfg: dict) -> Tuple[Params, str]:
    """Apply preset then explicit strategy overrides. Unknown keys raise (typos must not
    silently become no-ops in a trading system)."""
    fields = {f.name for f in dataclasses.fields(Params)}
    preset = str(cfg.get("preset") or "balanced")
    over: Dict[str, Any] = {}
    over.update({k: v for k, v in ((cfg.get("presets") or {}).get(preset) or {}).items() if k != "executor"})
    over.update(cfg.get("strategy") or {})
    bad = set(over) - fields
    if bad:
        raise ValueError(f"config.json: unknown strategy keys {sorted(bad)}")
    for k in ("mom_lookbacks", "mom_universe", "core_candidates"):
        if k in over and isinstance(over[k], list):
            over[k] = tuple(over[k])
    return Params(**over), preset


def executor_settings(cfg: dict) -> Dict[str, Any]:
    """defaults < preset's executor block < config executor block (non-null, non-default) < env."""
    out = dict(_EXEC_DEFAULTS)
    preset = str(cfg.get("preset") or "balanced")
    for k, v in (((cfg.get("presets") or {}).get(preset) or {}).get("executor") or {}).items():
        if k in out:
            out[k] = v
    for k, v in (cfg.get("executor") or {}).items():
        if k in out and v is not None and not (k in _PRESET_OVERRIDABLE and v == _EXEC_DEFAULTS[k]):
            out[k] = v
    for k in out:
        env = os.environ.get(k.upper(), "").strip()
        if env:
            try:
                out[k] = float(env)
            except ValueError:
                pass
    for k in ("max_drawdown_halt", "trade_window_min", "min_trade_dollars", "sim_start_cash", "live_min_paper_runs"):
        if out[k] is not None:
            out[k] = float(out[k])
    if out["max_capital"] is not None:
        out["max_capital"] = float(out["max_capital"])
    return out
