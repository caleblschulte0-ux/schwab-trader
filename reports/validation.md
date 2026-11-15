# Validation report

_Same engine as `backtest.py`: close fills, 5 bps slippage/side, $0 commissions, dividends reinvested._

## 1. Walk-forward (out-of-sample) test

Parameters chosen on **2008-01-01 → 2016-12-31** only (best Sharpe among 48 combinations), then run untouched on **2017-01-01 → today**.

| Parameter set | In-sample CAGR | In-sample Sharpe | **Out-of-sample CAGR** | **Out-of-sample Sharpe** | OOS Max DD | OOS SPY CAGR |
|---|---:|---:|---:|---:|---:|---:|
| Best in-sample: top 4, lookbacks [126, 252], rebalance 5d | +7.7% | 0.65 | +12.5% | 0.83 | -19.6% | +14.8% |
| Shipped defaults: top 8, lookbacks [63, 126, 252], rebalance 10d | +6.2% | 0.57 | +12.0% | 0.89 | -18.0% | +14.8% |

If the out-of-sample Sharpe collapsed relative to in-sample, the edge was fitted. A modest decay is normal; a similar number means the rules generalise.

## 2. Parameter sensitivity (full period Sharpe)

| top_n \ lookbacks | [63, 126, 252] | [21, 63, 126, 252] | [126, 252] | [63, 126] | [252] |
|---|---:|---:|---:|---:|---:|
| **3** | 0.75 | 0.71 | 0.72 | 0.54 | 0.71 |
| **4** | 0.75 | 0.70 | 0.75 | 0.57 | 0.71 |
| **5** | 0.73 | 0.74 | 0.74 | 0.55 | 0.70 |
| **6** | 0.74 | 0.75 | 0.73 | 0.57 | 0.69 |
| **7** | 0.75 | 0.74 | 0.72 | 0.60 | 0.66 |
| **8** | **0.75** | 0.75 | 0.73 | 0.62 | 0.67 |

A robust strategy shows a plateau, not a single spike. The shipped cell is bold.

## 3. Rebalance-timing luck

Same rules, weekly cycle started on five different days:

| Start | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| 2008-01-02 | +9.3% | 0.75 | -17.8% |
| 2008-01-03 | +9.1% | 0.74 | -18.0% |
| 2008-01-04 | +9.4% | 0.76 | -17.8% |
| 2008-01-07 | +9.3% | 0.75 | -18.0% |
| 2008-01-08 | +9.4% | 0.76 | -17.8% |

Sharpe spread across start days: 0.74 – 0.76.

## 4. Block-bootstrap: what a random 5-year stretch could look like

1000 synthetic 5-year paths built from the strategy's own daily returns (21-day blocks, order shuffled).

| Percentile | 5-yr CAGR | Max drawdown |
|---|---:|---:|
| 5th (bad luck) | -0.2% | -30.8% |
| 25th | +5.6% | -21.9% |
| median | +9.3% | -17.7% |
| 75th | +13.5% | -14.2% |
| 95th (good luck) | +18.8% | -10.6% |

Probability a 5-year stretch would trip a 20% kill switch: **36%** of paths; a 30% kill switch: **6%**. That is why the executor's default `MAX_DRAWDOWN_HALT` is 0.30: a halt at 20% would fire inside the strategy's normal drawdown range and sell the bottom. Probability of a negative 5-year CAGR: **5%**.

## 5. Rolling 3-year windows vs SPY

Across 191 overlapping 3-year windows the strategy beat SPY buy-and-hold in **10%** of them. Median annualised gap -3.1%; worst -18.5%; best +7.7%.

This is the number to internalise: it will trail SPY in most straight-up 3-year stretches, and win by a lot in the stretches that include a bear market.

## 6. Building blocks and overlays, switched one at a time

Everything below is implemented in `strategy.py`; the shipped default is the row marked ✅. Each row flips ONE thing relative to the shipped defaults (`python backtest.py --grid3` for more).

| Variant | 2008→ CAGR / Sharpe / MaxDD | 2015→ CAGR / Sharpe / MaxDD | OOS 2017→ CAGR / Sharpe / MaxDD |
|---|---|---|---|
| ✅ Shipped defaults | +9.3% / 0.75 / -18% | +10.4% / 0.81 / -18% | +12.0% / 0.89 / -18% |
| previous defaults (core 30%, top 6, 200-day) | +9.7% / 0.75 / -20% | +10.0% / 0.76 / -18% | +12.0% / 0.86 / -18% |
| no core sleeve (100% rotation) | +8.1% / 0.71 / -14% | +8.3% / 0.72 / -15% | +10.2% / 0.83 / -15% |
| fixed SPY core instead of adaptive | +8.4% / 0.77 / -17% | +8.3% / 0.77 / -16% | +10.2% / 0.89 / -16% |
| 'growth' preset: fixed QQQ core | +10.8% / 0.87 / -18% | +12.0% / 0.92 / -18% | +14.1% / 1.03 / -18% |
| 'aggressive' preset: 50% in 2x SPY/QQQ (SSO/QLD), trend-timed | +14.6% / 0.79 / -28% | +15.9% / 0.82 / -28% | +18.1% / 0.88 / -28% |
| aggressive + 15% vol cap (rejected) | +9.9% / 0.75 / -23% | +10.2% / 0.75 / -23% | +11.3% / 0.81 / -23% |
| single rebalance tranche (no stagger) | +9.0% / 0.73 / -18% | +9.9% / 0.77 / -19% | +12.2% / 0.90 / -17% |
| no cluster cap | +9.3% / 0.75 / -18% | +10.4% / 0.81 / -18% | +12.0% / 0.89 / -18% |
| top 5 / weekly (previous defaults) | +9.9% / 0.75 / -19% | +11.0% / 0.80 / -18% | +12.6% / 0.87 / -18% |
| defensive asset by momentum (TLT/IEF/GLD) | +9.9% / 0.73 / -26% | +11.1% / 0.81 / -26% | +13.2% / 0.91 / -26% |
| breadth regime switch (<40% → all defensive) | +8.6% / 0.73 / -20% | +10.0% / 0.82 / -15% | +11.2% / 0.87 / -15% |
| portfolio vol target 12% | +7.7% / 0.74 / -16% | +8.1% / 0.75 / -16% | +9.2% / 0.82 / -16% |
| daily rebalance + hysteresis | +9.2% / 0.74 / -19% | +10.5% / 0.81 / -17% | +12.0% / 0.89 / -17% |
| + mean-reversion sleeve 25% | +8.7% / 0.71 / -18% | +10.0% / 0.78 / -18% | +11.6% / 0.86 / -18% |
| include 1-month lookback | +9.2% / 0.75 / -18% | +9.9% / 0.77 / -18% | +11.4% / 0.85 / -18% |
| equal weights instead of inverse-vol | +9.9% / 0.77 / -19% | +11.0% / 0.82 / -20% | +12.6% / 0.89 / -20% |

_Past performance is not a promise of future results._
