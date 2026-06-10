# Track Record — Edge Analysis

_Updated 2026-06-10T12:35:23Z · source: signals/paper_account.json (paper / DRY_RUN)_

> ⚠️ **SAMPLE TOO SMALL (13 closed trades, need ≥20).** Everything below is DIRECTIONAL ONLY — not statistically conclusive. Do not change strategy parameters or go live off this. Let it gather a clean sample first.

## Headline

**Verdict: NEGATIVE EXPECTANCY ❌**  
**Closed trades:** 13   **Win rate:** 15%   **Total realized:** $-37.62  
**Expectancy (avg $/trade):** $-2.89   **Avg %/trade:** -3.88%  
**Avg win:** $+6.69   **Avg loss:** $-4.64   **Payoff ratio:** 1.44   **Profit factor:** 0.26  
**Max drawdown (realized):** $-37.62

## Entry slippage (stocks)

- **Fill vs brain's intended price:** -0.76% (n=4) — how much above the brain's limit we actually paid.
- **Fill vs last trade (spread proxy):** +1.78% (n=4) — paid spread on entry. Doubles round-trip; compare to your ~5–10% targets.

## Breakdowns

### By signal

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| sec_8k | 1 | 100% | $+2.45 | $+2.45 | $+2.45 | $+0.00 | ∞ |
| news_smallcap | 4 | 25% | $-0.38 | $-0.09 | $+2.45 | $-0.94 | 0.87 |
| untagged | 9 | 11% | $-37.24 | $-4.14 | $+10.92 | $-6.02 | 0.23 |

### By macro tape at entry

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| neutral | 1 | 0% | $-0.10 | $-0.10 | $+0.00 | $-0.10 | 0.00 |
| risk_on | 3 | 33% | $-0.28 | $-0.09 | $+2.45 | $-1.36 | 0.90 |
| untagged | 9 | 11% | $-37.24 | $-4.14 | $+10.92 | $-6.02 | 0.23 |

### By catalyst freshness

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| 12-48h | 1 | 0% | $-0.10 | $-0.10 | $+0.00 | $-0.10 | 0.00 |
| 2-12h | 3 | 33% | $-0.28 | $-0.09 | $+2.45 | $-1.36 | 0.90 |
| no-catalyst/untagged | 9 | 11% | $-37.24 | $-4.14 | $+10.92 | $-6.02 | 0.23 |

### By exit reason

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| q1 earnings presentation catalyst (june 9) has played out: stock popped +8.2% intraday on the event then fully reverted to -0.39% below avg entry ($15.52 vs $15.58 avg). quick-trade thesis was the earnings catalyst; that event has now occurred, neutral-sentiment result, pop faded with no follow-through. catalyst spent. | 1 | 100% | $+2.45 | $+2.45 | $+2.45 | $+0.00 | ∞ |
| quick-trade thesis dead: hc wainwright pt reiteration produced zero follow-through; reversed -8.24% on day 1; absent from candidates funnel across multiple consecutive runs. momentum gone, no new catalyst. not converting a failed breakout into a multi-month clinical hold. | 1 | 0% | $-0.10 | $-0.10 | $+0.00 | $-0.10 | 0.00 |
| brain SELL | 6 | 17% | $-12.06 | $-2.01 | $+10.92 | $-4.60 | 0.48 |
| quick-trade thesis failed: bought jun 5 on iv ketamine/clinical momentum; now 4 trading days with zero follow-through and -6.16% drift. prior web search confirmed negative equity and only 6-8 months cash runway, making a dilutive raise before the q3 2026 anda decision near-certain. the dilution overhang structurally caps any rally regardless of clinical progress. catalyst momentum is dead — this is not a drawdown sell; the capital structure thesis is broken. | 1 | 0% | $-12.95 | $-12.95 | $+0.00 | $-12.95 | 0.00 |
| hit stop | 4 | 0% | $-14.96 | $-3.74 | $+0.00 | $-3.74 | 0.00 |

### By kind

| Bucket | Trades | Win% | Total $ | Expectancy $ | Avg Win | Avg Loss | PF |
|--------|-------:|-----:|--------:|-------------:|--------:|---------:|---:|
| stock | 13 | 15% | $-37.62 | $-2.89 | $+6.69 | $-4.64 | 0.26 |

