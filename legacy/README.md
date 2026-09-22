# legacy/ — the Schwab + Claude-brain version (retired 2026-09)

Kept for reference only; nothing in here runs. This was the original design:
Schwab API (OAuth refresh token that expired every 7 days), a Claude "buy brain"
and "sell brain" picking small-cap catalyst trades, and a home-grown paper ledger.

Why it was retired (see `reports/track_record.md` in this folder):
- 14 closed paper trades, 14% win rate, -$2.92 expectancy per trade, profit factor 0.25.
- The executor froze for weeks every time the Schwab token expired.
- The brain froze whenever the Claude subscription hit its weekly quota.

The replacement (repo root) is a systematic ETF momentum strategy on Alpaca with a
backtest, no LLM in the trading loop, and static API keys.
