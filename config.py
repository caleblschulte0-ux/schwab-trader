"""config.json -> strategy.Params + executor settings. Env vars override executor settings."""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Any, Dict, Tuple

from strategy import Params

CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.json")
_EXEC_DEFAULTS: Dict[str, Any] = {
    "max_capital": None, "max_drawdown_halt": 0.30, "trade_window_min": 120.0,
    "min_trade_dollars": 5.0, "sim_start_cash": 1000.0,
}


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
    over.update((cfg.get("presets") or {}).get(preset) or {})
    over.update(cfg.get("strategy") or {})
    bad = set(over) - fields
    if bad:
        raise ValueError(f"config.json: unknown strategy keys {sorted(bad)}")
    for k in ("mom_lookbacks", "mom_universe"):
        if k in over and isinstance(over[k], list):
            over[k] = tuple(over[k])
    return Params(**over), preset


def executor_settings(cfg: dict) -> Dict[str, Any]:
    out = dict(_EXEC_DEFAULTS)
    for k, v in (cfg.get("executor") or {}).items():
        if k in out:
            out[k] = v
    for k in out:
        env = os.environ.get(k.upper(), "").strip()
        if env:
            try:
                out[k] = float(env)
            except ValueError:
                pass
    for k in ("max_drawdown_halt", "trade_window_min", "min_trade_dollars", "sim_start_cash"):
        if out[k] is not None:
            out[k] = float(out[k])
    if out["max_capital"] is not None:
        out["max_capital"] = float(out["max_capital"])
    return out
