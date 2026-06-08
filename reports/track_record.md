# Track Record — Edge Analysis

_Updated 2026-06-08T14:45:31Z · source: signals/paper_account.json (paper / DRY_RUN)_

> ⚠️ **SAMPLE TOO SMALL (6 closed trades, need ≥20).** Everything below is DIRECTIONAL ONLY — not statistically conclusive. Do not change strategy parameters or go live off this. Let it gather a clean sample first.

## Headline

**Verdict: NEGATIVE EXPECTANCY ❌**  
**Closed trades:** 6   **Win rate:** 0%   **Total realized:** $-26.20  
**Expectancy (avg $/trade):** $-4.37   **Avg %/trade:** -7.33%  
**Avg win:** $+0.00   **Avg loss:** $-4.37   **Payoff ratio:** 0.00   **Profit factor:** 0.00  
**Max drawdown (realized):** $-26.20

## Entry slippage (stocks)

- **Fill vs brain's intended price:** -10.07% (n=1) — how much above the brain's limit we actually paid.
- **Fill vs last trade (spread proxy):** +0.15% (n=1) — paid spread on entry. Doubles round-trip; compare to your ~5–10% targets.

## Breakdowns

### By signal

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| news_smallcap | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 5 | 0% | $-23.95 | $-4.79 | $+0.00 | $-4.79 | 0.00 |

### By macro tape at entry

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| risk_on | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| untagged | 5 | 0% | $-23.95 | $-4.79 | $+0.00 | $-4.79 | 0.00 |

### By catalyst freshness

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| 2-12h | 1 | 0% | $-2.25 | $-2.25 | $+0.00 | $-2.25 | 0.00 |
| no-catalyst/untagged | 5 | 0% | $-23.95 | $-4.79 | $+0.00 | $-4.79 | 0.00 |

### By exit reason

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| brain SELL | 2 | 0% | $-11.24 | $-5.62 | $+0.00 | $-5.62 | 0.00 |
| hit stop | 4 | 0% | $-14.96 | $-3.74 | $+0.00 | $-3.74 | 0.00 |

### By kind

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| stock | 6 | 0% | $-26.20 | $-4.37 | $+0.00 | $-4.37 | 0.00 |

