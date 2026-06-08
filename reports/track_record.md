# Track Record — Edge Analysis

_Updated 2026-06-08T20:15:25Z · source: signals/paper_account.json (paper / DRY_RUN)_

> ⚠️ **SAMPLE TOO SMALL (9 closed trades, need ≥20).** Everything below is DIRECTIONAL ONLY — not statistically conclusive. Do not change strategy parameters or go live off this. Let it gather a clean sample first.

## Headline

**Verdict: NEGATIVE EXPECTANCY ❌**  
**Closed trades:** 9   **Win rate:** 11%   **Total realized:** $-26.54  
**Expectancy (avg $/trade):** $-2.95   **Avg %/trade:** -4.77%  
**Avg win:** $+10.92   **Avg loss:** $-4.68   **Payoff ratio:** 2.33   **Profit factor:** 0.29  
**Max drawdown (realized):** $-26.54

## Entry slippage (stocks)

- **Fill vs brain's intended price:** -10.07% (n=1) — how much above the brain's limit we actually paid.
- **Fill vs last trade (spread proxy):** +0.15% (n=1) — paid spread on entry. Doubles round-trip; compare to your ~5–10% targets.

## Breakdowns

### By signal

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| news_smallcap | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By macro tape at entry

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| risk_on | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By catalyst freshness

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| 2-12h | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| no-catalyst/untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By exit reason

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| brain SELL | 5 | 20% | $-11.58 | $-2.32 | $+10.92 | $-5.62 | 0.49 |
| hit stop | 4 | 0% | $-14.96 | $-3.74 | $+0.00 | $-3.74 | 0.00 |

### By kind

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| stock | 9 | 11% | $-26.54 | $-2.95 | $+10.92 | $-4.68 | 0.29 |

