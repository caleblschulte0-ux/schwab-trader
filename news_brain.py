#!/usr/bin/env python3
"""News risk scan: headlines -> Claude -> a strictly validated, DEFENSIVE-ONLY verdict.

    python news_brain.py            # writes signals/news_risk.json (or nothing on failure)

The verdict can only reduce risk (a market risk level, and up to MAX_VETOES ETFs to avoid
today). It can never pick a buy. Every claim must cite headline ids that exist; claims
without evidence are dropped. If this script fails for ANY reason the executor trades
normally, so the bot never depends on it.

LLM backends, first one available wins:
  ANTHROPIC_API_KEY        -> Messages API over HTTPS (stdlib)
  CLAUDE_CODE_OAUTH_TOKEN  -> the `claude` CLI in print mode (subscription)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import news
from strategy import LEVERAGED, UNIVERSE

OUT = os.path.join("signals", "news_risk.json")
TARGETS = os.path.join("signals", "targets.json")
HOLDINGS = os.path.join("signals", "holdings.json")
MODEL = os.environ.get("NEWS_MODEL", "claude-sonnet-5")
MAX_VETOES = 3
MAX_HEADLINES = 160
ET = ZoneInfo("America/New_York")

PROMPT = """You are the RISK OFFICER for an automated ETF portfolio. You do not pick trades.
Your only powers are defensive: (a) set today's MARKET RISK LEVEL, which can shrink the
portfolio's risk exposure, and (b) VETO up to {max_vetoes} specific ETFs for today (no buying,
and trimmed to T-bills), because of concrete, material, NEW news that the ETF is directly
exposed to.

Be calibrated and conservative. Most days are level 0 with no vetoes. Markets already price
widely known news within minutes, so ordinary headlines (earnings beats, analyst notes,
routine Fed commentary, "stocks fall 1%") are NOT reasons to act. Act only on events whose
consequences are large, fresh (last ~24h) and plausibly not yet fully priced: e.g. a sudden
war or attack, a major bank or exchange failure, an emergency central-bank action, a
government default or shutdown shock, sweeping sanctions or export bans hitting a sector,
a criminal indictment or scandal at the top of a government or a mega-cap company that
dominates an ETF, a sector-wide regulatory ban, a fund-specific problem (closure, halt).

Levels: 0 = normal. 1 = elevated, informational only. 2 = high: a serious market-wide shock is
unfolding. 3 = severe: crisis-grade event (think 9/11, Lehman, March 2020 lockdowns).

TODAY (US/Eastern): {today}
PORTFOLIO THE BOT INTENDS TO HOLD (weights) and what each ETF is:
{portfolio}

HEADLINES (id | source | published UTC | text):
{headlines}

Reply with ONLY a JSON object, no prose, exactly this schema:
{{"market_risk": 0|1|2|3,
  "market_reason": "one sentence, or empty if 0",
  "market_evidence": [headline ids],
  "vetoes": [{{"symbol": "TICKER", "reason": "one sentence on the direct exposure", "evidence": [headline ids]}}],
  "summary": "two sentences max on what matters in today's news for this portfolio"}}
Vetoes may only name tickers from the portfolio list above."""


def _read(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def portfolio_view() -> Dict[str, float]:
    t = _read(TARGETS).get("weights") or {}
    h = {p["symbol"]: 0.0 for p in (_read(HOLDINGS).get("positions") or [])}
    out = {s: float(w) for s, w in t.items()}
    for s in h:
        out.setdefault(s, 0.0)
    return out


def build_prompt(heads: List[dict], port: Dict[str, float], today: str) -> str:
    plines = "\n".join(f"- {s} {w:.0%}: {news.ETF_THEMES.get(s, s)}" for s, w in sorted(port.items(), key=lambda x: -x[1])) or "- (none yet)"
    hlines = "\n".join(f"{h['id']} | {h['source']} | {(h.get('published') or '')[:16]} | {h['title']}" for h in heads[:MAX_HEADLINES])
    return PROMPT.format(max_vetoes=MAX_VETOES, today=today, portfolio=plines, headlines=hlines)


# ------------------------------------------------------------------ LLM backends
def call_api(prompt: str, key: str) -> str:
    body = json.dumps({"model": MODEL, "max_tokens": 1200, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.load(r)
    return "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")


def call_cli(prompt: str) -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude CLI not installed")
    r = subprocess.run([exe, "-p", prompt, "--model", "sonnet", "--output-format", "text", "--allowedTools", ""],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {(r.stderr or r.stdout)[-300:]}")
    return r.stdout


def ask(prompt: str) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return call_api(prompt, key)
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip():
        return call_cli(prompt)
    raise RuntimeError("no LLM credentials (ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN)")


# ------------------------------------------------------------------ validation
def parse_verdict(text: str, heads: List[dict], allowed: set) -> dict:
    """Strict: anything malformed, uncited, or out of bounds is dropped, never guessed."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    raw = json.loads(m.group(0))
    if not isinstance(raw, dict):
        raise ValueError("model reply is not a JSON object")
    ids = {h["id"]: h for h in heads}

    def cite(v) -> List[int]:
        if not isinstance(v, list):
            return []
        return [int(i) for i in v if str(i).isdigit() and int(i) in ids]

    level = raw.get("market_risk", 0)
    level = int(level) if str(level).isdigit() and 0 <= int(level) <= 3 else 0
    m_ev = cite(raw.get("market_evidence"))
    dropped: List[str] = []
    if level >= 2 and not m_ev:
        dropped.append(f"market_risk {level} had no valid evidence -> 0")
        level = 0
    vetoes = []
    raw_vetoes = raw.get("vetoes") if isinstance(raw.get("vetoes"), list) else []
    for v in raw_vetoes[:MAX_VETOES]:
        if not isinstance(v, dict):
            dropped.append("veto entry is not an object")
            continue
        sym = str(v.get("symbol", "")).upper().strip()
        ev = cite(v.get("evidence"))
        if sym not in allowed:
            dropped.append(f"veto {sym}: not an allowed symbol")
            continue
        if not ev:
            dropped.append(f"veto {sym}: no valid evidence")
            continue
        vetoes.append({"symbol": sym, "reason": str(v.get("reason", ""))[:300], "evidence": ev,
                       "headlines": [ids[i]["title"] for i in ev[:3]]})
    return {"market_risk": level, "market_reason": str(raw.get("market_reason", ""))[:300],
            "market_evidence": m_ev, "market_headlines": [ids[i]["title"] for i in m_ev[:3]],
            "vetoes": vetoes, "summary": str(raw.get("summary", ""))[:500], "dropped": dropped}


def main() -> int:
    now = datetime.now(timezone.utc)
    today = now.astimezone(ET).strftime("%Y-%m-%d")
    prev = _read(OUT)
    if prev.get("date") == today and not os.environ.get("NEWS_FORCE"):
        try:
            age_min = (now - datetime.strptime(prev["generated_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 60
        except (KeyError, ValueError):
            age_min = 1e9
        if age_min < 90:
            print(f"(news) verdict for {today} is {age_min:.0f} min old; reusing (one LLM call per day)")
            return 0
    port = portfolio_view()
    syms = set(port) | {"SPY", "QQQ"}
    heads = news.collect(syms)
    print(f"(news) {len(heads)} headlines")
    if len(heads) < 10:
        print("(news) too few headlines; no verdict (bot trades normally)")
        return 0
    allowed = (set(port) | set(UNIVERSE) | set(LEVERAGED.values())) - {"BIL"}
    try:
        verdict = parse_verdict(ask(build_prompt(heads, port, today)), heads, allowed)
    except Exception as exc:  # noqa: BLE001
        print(f"(news) no verdict: {exc} (bot trades normally)")
        return 0
    verdict.update({"date": today, "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "n_headlines": len(heads), "model": MODEL})
    os.makedirs("signals", exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(verdict, f, indent=2)
        f.write("\n")
    print(f"(news) market_risk={verdict['market_risk']} vetoes={[v['symbol'] for v in verdict['vetoes']]} :: {verdict['summary']}")
    for d in verdict["dropped"]:
        print(f"(news) dropped: {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
