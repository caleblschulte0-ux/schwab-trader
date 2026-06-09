# Track Record — Edge Analysis

_Updated 2026-06-09T12:35:24Z · source: signals/paper_account.json (paper / DRY_RUN)_

> ⚠️ **SAMPLE TOO SMALL (10 closed trades, need ≥20).** Everything below is DIRECTIONAL ONLY — not statistically conclusive. Do not change strategy parameters or go live off this. Let it gather a clean sample first.

## Headline

**Verdict: NEGATIVE EXPECTANCY ❌**  
**Closed trades:** 10   **Win rate:** 10%   **Total realized:** $-27.02  
**Expectancy (avg $/trade):** $-2.70   **Avg %/trade:** -4.38%  
**Avg win:** $+10.92   **Avg loss:** $-4.22   **Payoff ratio:** 2.59   **Profit factor:** 0.29  
**Max drawdown (realized):** $-27.02

## Entry slippage (stocks)

- **Fill vs brain's intended price:** -5.19% (n=2) — how much above the brain's limit we actually paid.
- **Fill vs last trade (spread proxy):** +0.23% (n=2) — paid spread on entry. Doubles round-trip; compare to your ~5–10% targets.

## Breakdowns

### By signal

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| news_smallcap | 2 | 0% | $-2.73 | $-1.36 | $+0.00 | $-1.36 | 0.00 |
| untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By macro tape at entry

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| risk_on | 2 | 0% | $-2.73 | $-1.36 | $+0.00 | $-1.36 | 0.00 |
| untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By catalyst freshness

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| 2-12h | 2 | 0% | $-2.73 | $-1.36 | $+0.00 | $-1.36 | 0.00 |
| no-catalyst/untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By exit reason

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| brain SELL | 6 | 17% | $-12.06 | $-2.01 | $+10.92 | $-4.60 | 0.48 |
| hit stop | 4 | 0% | $-14.96 | $-3.74 | $+0.00 | $-3.74 | 0.00 |

### By kind

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| stock | 10 | 10% | $-27.02 | $-2.70 | $+10.92 | $-4.22 | 0.29 |

