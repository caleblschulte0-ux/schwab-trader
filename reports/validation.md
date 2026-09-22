# Validation report

_Same engine as `backtest.py`: close fills, 5 bps slippage/side, $0 commissions, dividends reinvested._

## 1. Walk-forward (out-of-sample) test

Parameters chosen on **2008-01-01 → 2016-12-31** only (best Sharpe among 48 combinations), then run untouched on **2017-01-01 → today**.

| Parameter set | In-sample CAGR | In-sample Sharpe | **Out-of-sample CAGR** | **Out-of-sample Sharpe** | OOS Max DD | OOS SPY CAGR |
|---|---:|---:|---:|---:|---:|---:|
| Best in-sample: top 4, lookbacks [126, 252], rebalance 5d | +7.7% | 0.65 | +14.2% | 0.93 | -19.6% | +15.4% |
| Shipped defaults: top 8, lookbacks [63, 126, 252], rebalance 10d | +6.2% | 0.57 | +13.1% | 0.96 | -18.0% | +15.4% |

If the out-of-sample Sharpe collapsed relative to in-sample, the edge was fitted. A modest decay is normal; a similar number means the rules generalise.

## 2. Parameter sensitivity (full period Sharpe)

| top_n \ lookbacks | [63, 126, 252] | [21, 63, 126, 252] | [126, 252] | [63, 126] | [252] |
|---|---:|---:|---:|---:|---:|
| **3** | 0.80 | 0.76 | 0.77 | 0.58 | 0.76 |
| **4** | 0.80 | 0.75 | 0.80 | 0.61 | 0.76 |
| **5** | 0.78 | 0.78 | 0.79 | 0.60 | 0.75 |
| **6** | 0.78 | 0.79 | 0.78 | 0.62 | 0.73 |
| **7** | 0.79 | 0.78 | 0.76 | 0.64 | 0.70 |
| **8** | **0.79** | 0.78 | 0.78 | 0.66 | 0.71 |

A robust strategy shows a plateau, not a single spike. The shipped cell is bold.

## 3. Rebalance-timing luck

Same rules, weekly cycle started on five different days:

| Start | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| 2008-01-02 | +9.8% | 0.79 | -17.8% |
| 2008-01-03 | +9.7% | 0.78 | -18.0% |
| 2008-01-04 | +10.0% | 0.80 | -17.8% |
| 2008-01-07 | +9.8% | 0.79 | -18.0% |
| 2008-01-08 | +10.0% | 0.80 | -17.8% |

Sharpe spread across start days: 0.78 – 0.80.

## 4. Block-bootstrap: what a random 5-year stretch could look like

1000 synthetic 5-year paths built from the strategy's own daily returns (21-day blocks, order shuffled).

| Percentile | 5-yr CAGR | Max drawdown |
|---|---:|---:|
| 5th (bad luck) | +0.4% | -29.0% |
| 25th | +6.2% | -21.7% |
| median | +9.8% | -17.3% |
| 75th | +13.9% | -13.9% |
| 95th (good luck) | +18.5% | -10.7% |

Probability a 5-year stretch would trip a 20% kill switch: **34%** of paths; a 30% kill switch: **5%**. That is why the executor's default `MAX_DRAWDOWN_HALT` is 0.30: a halt at 20% would fire inside the strategy's normal drawdown range and sell the bottom. Probability of a negative 5-year CAGR: **4%**.

## 5. Rolling 3-year windows vs SPY

Across 189 overlapping 3-year windows the strategy beat SPY buy-and-hold in **10%** of them. Median annualised gap -3.1%; worst -18.5%; best +7.7%.

This is the number to internalise: it will trail SPY in most straight-up 3-year stretches, and win by a lot in the stretches that include a bear market.

## 6. Building blocks and overlays, switched one at a time

Everything below is implemented in `strategy.py`; the shipped default is the row marked ✅. Each row flips ONE thing relative to the shipped defaults (`python backtest.py --grid3` for more).

| Variant | 2008→ CAGR / Sharpe / MaxDD | 2015→ CAGR / Sharpe / MaxDD | OOS 2017→ CAGR / Sharpe / MaxDD |
|---|---|---|---|
| ✅ Shipped defaults | +9.8% / 0.79 / -18% | +11.3% / 0.87 / -18% | +13.1% / 0.96 / -18% |
| previous defaults (core 30%, top 6, 200-day) | +10.2% / 0.79 / -20% | +10.8% / 0.82 / -18% | +13.0% / 0.92 / -18% |
| no core sleeve (100% rotation) | +8.5% / 0.74 / -14% | +8.7% / 0.75 / -15% | +10.7% / 0.87 / -15% |
| fixed SPY core instead of adaptive | +8.7% / 0.80 / -17% | +8.8% / 0.81 / -16% | +10.9% / 0.94 / -16% |
| 'growth' preset: fixed QQQ core | +11.3% / 0.90 / -18% | +12.7% / 0.97 / -18% | +15.0% / 1.09 / -18% |
| 'aggressive' preset: 50% in 2x SPY/QQQ (SSO/QLD), trend-timed | +15.6% / 0.83 / -28% | +17.4% / 0.89 / -28% | +20.0% / 0.96 / -28% |
| aggressive + 15% vol cap (rejected) | +10.7% / 0.80 / -23% | +11.3% / 0.82 / -23% | +12.7% / 0.90 / -23% |
| single rebalance tranche (no stagger) | +9.6% / 0.77 / -18% | +10.8% / 0.83 / -19% | +13.3% / 0.97 / -17% |
| no cluster cap | +9.8% / 0.79 / -18% | +11.3% / 0.87 / -18% | +13.1% / 0.96 / -18% |
| top 5 / weekly (previous defaults) | +10.5% / 0.79 / -19% | +12.0% / 0.87 / -18% | +13.9% / 0.95 / -18% |
| defensive asset by momentum (TLT/IEF/GLD) | +10.5% / 0.77 / -26% | +12.0% / 0.87 / -26% | +14.4% / 0.97 / -26% |
| breadth regime switch (<40% → all defensive) | +9.1% / 0.77 / -20% | +10.9% / 0.88 / -15% | +12.3% / 0.94 / -15% |
| portfolio vol target 12% | +8.2% / 0.78 / -16% | +8.9% / 0.82 / -16% | +10.2% / 0.90 / -16% |
| daily rebalance + hysteresis | +9.8% / 0.78 / -19% | +11.4% / 0.87 / -17% | +13.1% / 0.96 / -17% |
| + mean-reversion sleeve 25% | +9.3% / 0.75 / -18% | +10.9% / 0.84 / -18% | +12.8% / 0.93 / -18% |
| include 1-month lookback | +9.7% / 0.78 / -18% | +10.6% / 0.83 / -18% | +12.4% / 0.91 / -18% |
| equal weights instead of inverse-vol | +10.5% / 0.81 / -19% | +12.0% / 0.88 / -20% | +13.7% / 0.96 / -20% |

_Past performance is not a promise of future results._
