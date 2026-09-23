"""Headline collection (keyless RSS). Pure stdlib. Returns a de-duplicated, numbered list.

Sources: Google News search RSS (market-wide queries + one per held/target ETF theme),
Yahoo Finance per-ticker RSS, MarketWatch top stories. Any source can fail; the rest still count.
"""
from __future__ import annotations

import email.utils
import html
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

UA = {"User-Agent": "Mozilla/5.0 (compatible; etf-bot/1.0)"}

MARKET_QUERIES = [
    "stock market", "Federal Reserve", "treasury yields", "oil prices", "recession",
    "tariffs", "geopolitical", "bank failure", "indictment OR impeachment OR sanctions",
]

# What each ETF actually is, so the model can map events to exposure.
ETF_THEMES: Dict[str, str] = {
    "SPY": "S&P 500", "QQQ": "Nasdaq-100 big tech", "IWM": "US small caps", "DIA": "Dow Jones 30",
    "MDY": "US mid caps", "XLK": "US technology sector", "XLF": "US banks and financials",
    "XLE": "US oil and gas companies", "XLV": "US healthcare", "XLI": "US industrials",
    "XLY": "US consumer discretionary (Amazon, Tesla)", "XLP": "US consumer staples",
    "XLU": "US utilities", "XLB": "US materials and chemicals", "XLRE": "US real estate",
    "XLC": "US communication services (Meta, Google)", "SMH": "semiconductors (Nvidia, TSMC)",
    "XBI": "small biotech", "VNQ": "US REITs", "EFA": "developed markets ex-US",
    "EEM": "emerging markets", "VGK": "European stocks", "EWJ": "Japanese stocks",
    "FXI": "Chinese large caps", "TLT": "long-term US treasuries", "IEF": "7-10 year treasuries",
    "LQD": "investment-grade corporate bonds", "HYG": "junk bonds", "SHY": "short treasuries",
    "BIL": "T-bills (cash)", "GLD": "gold", "SLV": "silver", "DBC": "broad commodities",
    "USO": "crude oil futures", "UUP": "US dollar", "SSO": "2x S&P 500", "QLD": "2x Nasdaq-100",
}


def _get(url: str, timeout: int = 15) -> Optional[bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return None


def parse_rss(raw: bytes, source: str) -> List[dict]:
    out: List[dict] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        if not title:
            continue
        pub = it.findtext("pubDate") or ""
        try:
            ts = email.utils.parsedate_to_datetime(pub).astimezone(timezone.utc)
        except (TypeError, ValueError):
            ts = None
        src = it.findtext("source") or source
        out.append({"title": re.sub(r"\s+", " ", title), "source": src.strip(), "published": ts.isoformat() if ts else None})
    return out


def _norm(t: str) -> str:
    t = re.sub(r"\s+-\s+[^-]{2,40}$", "", t.lower())  # drop " - Reuters" suffixes
    return re.sub(r"[^a-z0-9 ]", "", t)[:90]


def collect(symbols: Iterable[str] = (), max_age_hours: float = 30.0, per_query: int = 12,
            fetch=_get, now: Optional[datetime] = None) -> List[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    items: List[dict] = []
    for q in MARKET_QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": f"{q} when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        raw = fetch(url)
        if raw:
            items += [dict(x, topic=q) for x in parse_rss(raw, "Google News")[:per_query]]
    syms = sorted(set(symbols) - {"BIL"})
    for s in syms:
        theme = ETF_THEMES.get(s)
        if theme:
            url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
                {"q": f"{theme} when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
            raw = fetch(url)
            if raw:
                items += [dict(x, topic=s) for x in parse_rss(raw, "Google News")[:6]]
    if syms:
        raw = fetch("https://feeds.finance.yahoo.com/rss/2.0/headline?" + urllib.parse.urlencode(
            {"s": ",".join(syms[:20]), "region": "US", "lang": "en-US"}))
        if raw:
            items += [dict(x, topic="yahoo") for x in parse_rss(raw, "Yahoo Finance")[:25]]
    raw = fetch("https://feeds.content.dowjones.io/public/rss/mw_topstories")
    if raw:
        items += [dict(x, topic="marketwatch") for x in parse_rss(raw, "MarketWatch")[:20]]
    seen = set()
    out: List[dict] = []
    for x in items:
        if x.get("published"):
            try:
                if datetime.fromisoformat(x["published"]) < cutoff:
                    continue
            except ValueError:
                pass
        k = _norm(x["title"])
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    for i, x in enumerate(out, 1):
        x["id"] = i
    return out
