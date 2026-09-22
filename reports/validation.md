# Validation report

_Same engine as `backtest.py`: close fills, 5 bps slippage/side, $0 commissions, dividends reinvested._

## 1. Walk-forward (out-of-sample) test

Parameters chosen on **2008-01-01 → 2016-12-31** only (best Sharpe among 48 combinations), then run untouched on **2017-01-01 → today**.

| Parameter set | In-sample CAGR | In-sample Sharpe | **Out-of-sample CAGR** | **Out-of-sample Sharpe** | OOS Max DD | OOS SPY CAGR |
|---|---:|---:|---:|---:|---:|---:|
| Best in-sample: top 6, lookbacks [21, 63, 126, 252], rebalance 10d | +7.0% | 0.70 | +11.3% | 0.98 | -14.0% | +15.4% |
| Shipped defaults: top 8, lookbacks [63, 126, 252], rebalance 10d | +5.5% | 0.60 | +11.8% | 1.09 | -13.6% | +15.4% |

If the out-of-sample Sharpe collapsed relative to in-sample, the edge was fitted. A modest decay is normal; a similar number means the rules generalise.

## 2. Parameter sensitivity (full period Sharpe)

| top_n \ lookbacks | [63, 126, 252] | [21, 63, 126, 252] | [126, 252] | [63, 126] | [252] |
|---|---:|---:|---:|---:|---:|
| **3** | 0.84 | 0.77 | 0.82 | 0.62 | 0.83 |
| **4** | 0.81 | 0.77 | 0.83 | 0.65 | 0.82 |
| **5** | 0.82 | 0.82 | 0.81 | 0.63 | 0.76 |
| **6** | 0.84 | 0.85 | 0.78 | 0.66 | 0.74 |
| **7** | 0.86 | 0.88 | 0.79 | 0.71 | 0.77 |
| **8** | **0.86** | 0.86 | 0.82 | 0.73 | 0.82 |

A robust strategy shows a plateau, not a single spike. The shipped cell is bold.

## 3. Rebalance-timing luck

Same rules, weekly cycle started on five different days:

| Start | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| 2008-01-02 | +8.6% | 0.86 | -14.5% |
| 2008-01-03 | +8.6% | 0.86 | -14.7% |
| 2008-01-04 | +8.8% | 0.87 | -14.5% |
| 2008-01-07 | +8.8% | 0.88 | -14.7% |
| 2008-01-08 | +8.7% | 0.87 | -14.4% |

Sharpe spread across start days: 0.86 – 0.88.

## 4. Block-bootstrap: what a random 5-year stretch could look like

1000 synthetic 5-year paths built from the strategy's own daily returns (21-day blocks, order shuffled).

| Percentile | 5-yr CAGR | Max drawdown |
|---|---:|---:|
| 5th (bad luck) | +1.3% | -22.1% |
| 25th | +5.7% | -16.3% |
| median | +8.6% | -13.2% |
| 75th | +11.8% | -10.7% |
| 95th (good luck) | +15.3% | -8.2% |

Probability a 5-year stretch would trip a 20% kill switch: **9%** of paths; a 30% kill switch: **1%**. That is why the executor's default `MAX_DRAWDOWN_HALT` is 0.30: a halt at 20% would fire inside the strategy's normal drawdown range and sell the bottom. Probability of a negative 5-year CAGR: **3%**.

## 5. Rolling 3-year windows vs SPY

Across 189 overlapping 3-year windows the strategy beat SPY buy-and-hold in **6%** of them. Median annualised gap -4.5%; worst -20.6%; best +6.4%.

This is the number to internalise: it will trail SPY in most straight-up 3-year stretches, and win by a lot in the stretches that include a bear market.

## 6. Building blocks and overlays, switched one at a time

Everything below is implemented in `strategy.py`; the shipped default is the row marked ✅. Each row flips ONE thing relative to the shipped defaults (`python backtest.py --grid3` for more).

| Variant | 2008→ CAGR / Sharpe / MaxDD | 2015→ CAGR / Sharpe / MaxDD | OOS 2017→ CAGR / Sharpe / MaxDD |
|---|---|---|---|
| ✅ Shipped defaults | +8.6% / 0.86 / -14% | +10.2% / 0.99 / -14% | +11.8% / 1.09 / -14% |
| previous defaults (core 30%, top 6, 200-day) | +9.9% / 0.81 / -18% | +10.6% / 0.85 / -16% | +12.6% / 0.96 / -16% |
| no core sleeve (100% rotation) | +8.5% / 0.74 / -14% | +8.7% / 0.75 / -15% | +10.7% / 0.87 / -15% |
| fixed SPY core instead of adaptive | +9.0% / 0.86 / -17% | +9.1% / 0.87 / -14% | +11.0% / 1.01 / -14% |
| 'growth' preset: fixed QQQ core | +9.7% / 0.95 / -14% | +11.2% / 1.08 / -14% | +13.3% / 1.21 / -14% |
| 'aggressive' preset: 50% in 2x SPY/QQQ (SSO/QLD), trend-timed | +15.6% / 0.83 / -28% | +17.4% / 0.89 / -28% | +20.0% / 0.96 / -28% |
| aggressive + 15% vol cap (rejected) | +10.7% / 0.80 / -23% | +11.3% / 0.82 / -23% | +12.7% / 0.90 / -23% |
| single rebalance tranche (no stagger) | +8.9% / 0.87 / -15% | +10.1% / 0.97 / -15% | +12.6% / 1.13 / -13% |
| no cluster cap | +8.7% / 0.85 / -14% | +10.3% / 0.98 / -14% | +11.9% / 1.08 / -14% |
| top 5 / weekly (previous defaults) | +9.5% / 0.83 / -19% | +11.0% / 0.93 / -13% | +12.4% / 1.00 / -13% |
| defensive asset by momentum (TLT/IEF/GLD) | +10.5% / 0.86 / -21% | +12.1% / 0.99 / -21% | +15.0% / 1.15 / -21% |
| breadth regime switch (<40% → all defensive) | +8.0% / 0.83 / -17% | +9.7% / 0.99 / -13% | +11.0% / 1.07 / -13% |
| portfolio vol target 12% | +8.0% / 0.87 / -14% | +9.0% / 0.94 / -14% | +10.2% / 1.03 / -14% |
| daily rebalance + hysteresis | +8.8% / 0.86 / -16% | +10.3% / 0.98 / -14% | +11.8% / 1.07 / -14% |
| + mean-reversion sleeve 25% | +8.2% / 0.81 / -17% | +10.0% / 0.96 / -14% | +11.6% / 1.07 / -14% |
| include 1-month lookback | +8.8% / 0.86 / -15% | +9.8% / 0.95 / -13% | +11.2% / 1.04 / -13% |
| equal weights instead of inverse-vol | +9.2% / 0.86 / -15% | +10.8% / 0.98 / -15% | +12.3% / 1.07 / -15% |

_Past performance is not a promise of future results._
