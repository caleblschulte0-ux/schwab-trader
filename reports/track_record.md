# Track Record — Edge Analysis

_Updated 2026-06-08T15:55:29Z · source: signals/paper_account.json (paper / DRY_RUN)_

> ⚠️ **SAMPLE TOO SMALL (7 closed trades, need ≥20).** Everything below is DIRECTIONAL ONLY — not statistically conclusive. Do not change strategy parameters or go live off this. Let it gather a clean sample first.

## Headline

**Verdict: NEGATIVE EXPECTANCY ❌**  
**Closed trades:** 7   **Win rate:** 14%   **Total realized:** $-15.28  
**Expectancy (avg $/trade):** $-2.18   **Avg %/trade:** -3.60%  
**Avg win:** $+10.92   **Avg loss:** $-4.37   **Payoff ratio:** 2.50   **Profit factor:** 0.42  
**Max drawdown (realized):** $-26.20

## Entry slippage (stocks)

- **Fill vs brain's intended price:** -10.07% (n=1) — how much above the brain's limit we actually paid.
- **Fill vs last trade (spread proxy):** +0.15% (n=1) — paid spread on entry. Doubles round-trip; compare to your ~5–10% targets.

## Breakdowns

### By signal

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| news_smallcap | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 6 | 17% | $-13.03 | $-2.17 | $+10.92 | $-4.79 | 0.46 |

### By macro tape at entry

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| risk_on | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 6 | 17% | $-13.03 | $-2.17 | $+10.92 | $-4.79 | 0.46 |

### By catalyst freshness

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| 2-12h | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| no-catalyst/untagged | 6 | 17% | $-13.03 | $-2.17 | $+10.92 | $-4.79 | 0.46 |

### By exit reason

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| brain SELL | 3 | 33% | $-0.32 | $-0.11 | $+10.92 | $-5.62 | 0.97 |
| hit stop | 4 | 0% | $-14.96 | $-3.74 | $+0.00 | $-3.74 | 0.00 |

### By kind

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| stock | 7 | 14% | $-15.28 | $-2.18 | $+10.92 | $-4.37 | 0.42 |

