# Track Record — Edge Analysis

_Updated 2026-06-08T17:10:25Z · source: signals/paper_account.json (paper / DRY_RUN)_

> ⚠️ **SAMPLE TOO SMALL (8 closed trades, need ≥20).** Everything below is DIRECTIONAL ONLY — not statistically conclusive. Do not change strategy parameters or go live off this. Let it gather a clean sample first.

## Headline

**Verdict: NEGATIVE EXPECTANCY ❌**  
**Closed trades:** 8   **Win rate:** 12%   **Total realized:** $-21.70  
**Expectancy (avg $/trade):** $-2.71   **Avg %/trade:** -4.42%  
**Avg win:** $+10.92   **Avg loss:** $-4.66   **Payoff ratio:** 2.34   **Profit factor:** 0.33  
**Max drawdown (realized):** $-26.20

## Entry slippage (stocks)

- **Fill vs brain's intended price:** -10.07% (n=1) — how much above the brain's limit we actually paid.
- **Fill vs last trade (spread proxy):** +0.15% (n=1) — paid spread on entry. Doubles round-trip; compare to your ~5–10% targets.

## Breakdowns

### By signal

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| news_smallcap | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 7 | 14% | $-19.45 | $-2.78 | $+10.92 | $-5.06 | 0.36 |

### By macro tape at entry

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| risk_on | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 7 | 14% | $-19.45 | $-2.78 | $+10.92 | $-5.06 | 0.36 |

### By catalyst freshness

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| 2-12h | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| no-catalyst/untagged | 7 | 14% | $-19.45 | $-2.78 | $+10.92 | $-5.06 | 0.36 |

### By exit reason

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| brain SELL | 4 | 25% | $-6.74 | $-1.69 | $+10.92 | $-5.89 | 0.62 |
| hit stop | 4 | 0% | $-14.96 | $-3.74 | $+0.00 | $-3.74 | 0.00 |

### By kind

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| stock | 8 | 12% | $-21.70 | $-2.71 | $+10.92 | $-4.66 | 0.33 |

