# Track Record — Edge Analysis

_Updated 2026-06-09T20:45:28Z · source: signals/paper_account.json (paper / DRY_RUN)_

> ⚠️ **SAMPLE TOO SMALL (11 closed trades, need ≥20).** Everything below is DIRECTIONAL ONLY — not statistically conclusive. Do not change strategy parameters or go live off this. Let it gather a clean sample first.

## Headline

**Verdict: NEGATIVE EXPECTANCY ❌**  
**Closed trades:** 11   **Win rate:** 18%   **Total realized:** $-24.57  
**Expectancy (avg $/trade):** $-2.23   **Avg %/trade:** -3.77%  
**Avg win:** $+6.69   **Avg loss:** $-4.22   **Payoff ratio:** 1.59   **Profit factor:** 0.35  
**Max drawdown (realized):** $-27.02

## Entry slippage (stocks)

- **Fill vs brain's intended price:** -2.74% (n=3) — how much above the brain's limit we actually paid.
- **Fill vs last trade (spread proxy):** +0.34% (n=3) — paid spread on entry. Doubles round-trip; compare to your ~5–10% targets.

## Breakdowns

### By signal

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| sec_8k | 1 | 100% | $+2.45 | $+2.45 | $+2.45 | $+0.00 | ∞ |
| news_smallcap | 3 | 33% | $-0.28 | $-0.09 | $+2.45 | $-1.36 | 0.90 |
| untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By macro tape at entry

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| risk_on | 3 | 33% | $-0.28 | $-0.09 | $+2.45 | $-1.36 | 0.90 |
| untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By catalyst freshness

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| 2-12h | 3 | 33% | $-0.28 | $-0.09 | $+2.45 | $-1.36 | 0.90 |
| no-catalyst/untagged | 8 | 12% | $-24.29 | $-3.04 | $+10.92 | $-5.03 | 0.31 |

### By exit reason

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| q1 earnings presentation catalyst (june 9) has played out: stock popped +8.2% intraday on the event then fully reverted to -0.39% below avg entry ($15.52 vs $15.58 avg). quick-trade thesis was the earnings catalyst; that event has now occurred, neutral-sentiment result, pop faded with no follow-through. catalyst spent. | 1 | 100% | $+2.45 | $+2.45 | $+2.45 | $+0.00 | ∞ |
| brain SELL | 6 | 17% | $-12.06 | $-2.01 | $+10.92 | $-4.60 | 0.48 |
| hit stop | 4 | 0% | $-14.96 | $-3.74 | $+0.00 | $-3.74 | 0.00 |

### By kind

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| stock | 11 | 18% | $-24.57 | $-2.23 | $+6.69 | $-4.22 | 0.35 |

