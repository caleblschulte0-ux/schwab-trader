# Validation report

_Same engine as `backtest.py`: close fills, 5 bps slippage/side, $0 commissions, dividends reinvested._

## 1. Walk-forward (out-of-sample) test

Parameters chosen on **2008-01-01 → 2016-12-31** only (best Sharpe among 60 combinations), then run untouched on **2017-01-01 → today**.

| Parameter set | In-sample CAGR | In-sample Sharpe | **Out-of-sample CAGR** | **Out-of-sample Sharpe** | OOS Max DD | OOS SPY CAGR |
|---|---:|---:|---:|---:|---:|---:|
| Best in-sample: top 6, lookbacks [63, 126, 252], rebalance 5d | +7.5% | 0.69 | +11.1% | 0.92 | -15.2% | +15.4% |
| Shipped defaults: top 6, lookbacks [63, 126, 252], rebalance 10d | +7.4% | 0.68 | +11.8% | 0.97 | -16.0% | +15.4% |

If the out-of-sample Sharpe collapsed relative to in-sample, the edge was fitted. A modest decay is normal; a similar number means the rules generalise.

## 2. Parameter sensitivity (full period Sharpe)

| top_n \ lookbacks | [63, 126, 252] | [21, 63, 126, 252] | [126, 252] | [63, 126] | [252] |
|---|---:|---:|---:|---:|---:|
| **3** | 0.71 | 0.73 | 0.77 | 0.69 | 0.78 |
| **4** | 0.74 | 0.71 | 0.81 | 0.69 | 0.85 |
| **5** | 0.80 | 0.79 | 0.81 | 0.70 | 0.83 |
| **6** | **0.82** | 0.80 | 0.85 | 0.69 | 0.80 |
| **7** | 0.82 | 0.82 | 0.82 | 0.75 | 0.79 |
| **8** | 0.81 | 0.80 | 0.78 | 0.78 | 0.80 |

A robust strategy shows a plateau, not a single spike. The shipped cell is bold.

## 3. Rebalance-timing luck

Same rules, weekly cycle started on five different days:

| Start | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| 2008-01-02 | +9.4% | 0.82 | -16.9% |
| 2008-01-03 | +8.8% | 0.77 | -16.3% |
| 2008-01-04 | +8.8% | 0.77 | -16.9% |
| 2008-01-07 | +8.6% | 0.75 | -16.0% |
| 2008-01-08 | +9.4% | 0.80 | -17.0% |

Sharpe spread across start days: 0.75 – 0.82.

## 4. Block-bootstrap: what a random 5-year stretch could look like

1000 synthetic 5-year paths built from the strategy's own daily returns (21-day blocks, order shuffled).

| Percentile | 5-yr CAGR | Max drawdown |
|---|---:|---:|
| 5th (bad luck) | +1.4% | -25.2% |
| 25th | +6.3% | -18.4% |
| median | +9.6% | -14.7% |
| 75th | +12.8% | -12.2% |
| 95th (good luck) | +17.8% | -9.6% |

Probability a 5-year stretch would trip a 20% kill switch: **18%** of paths; a 30% kill switch: **2%**. That is why the executor's default `MAX_DRAWDOWN_HALT` is 0.30: a halt at 20% would fire inside the strategy's normal drawdown range and sell the bottom. Probability of a negative 5-year CAGR: **3%**.

## 5. Rolling 3-year windows vs SPY

Across 189 overlapping 3-year windows the strategy beat SPY buy-and-hold in **6%** of them. Median annualised gap -5.3%; worst -20.9%; best +9.9%.

This is the number to internalise: it will trail SPY in most straight-up 3-year stretches, and win by a lot in the stretches that include a bear market.

## 6. Building blocks and overlays, switched one at a time

Everything below is implemented in `strategy.py`; the shipped default is the row marked ✅. Each row flips ONE thing relative to the shipped defaults (`python backtest.py --grid3` for more).

| Variant | 2008→ CAGR / Sharpe / MaxDD | 2015→ CAGR / Sharpe / MaxDD | OOS 2017→ CAGR / Sharpe / MaxDD |
|---|---|---|---|
| ✅ Shipped defaults | +9.4% / 0.82 / -17% | +9.0% / 0.79 / -16% | +11.8% / 0.97 / -16% |
| no SPY core sleeve (100% rotation) | +9.7% / 0.75 / -17% | +8.5% / 0.67 / -17% | +12.1% / 0.88 / -17% |
| 'growth' preset: QQQ core instead of SPY | +10.2% / 0.84 / -18% | +10.3% / 0.84 / -17% | +13.7% / 1.05 / -16% |
| no cluster cap | +9.8% / 0.82 / -19% | +9.4% / 0.79 / -16% | +12.2% / 0.96 / -16% |
| top 5 / weekly (previous defaults) | +9.8% / 0.80 / -17% | +10.0% / 0.83 / -16% | +11.0% / 0.87 / -15% |
| defensive asset by momentum (TLT/IEF/GLD) | +10.1% / 0.79 / -21% | +9.1% / 0.74 / -23% | +13.1% / 0.98 / -20% |
| breadth regime switch (<40% → all defensive) | +8.3% / 0.76 / -18% | +9.8% / 0.88 / -15% | +12.7% / 1.07 / -14% |
| portfolio vol target 12% | +8.3% / 0.81 / -15% | +7.5% / 0.73 / -15% | +9.9% / 0.93 / -14% |
| daily rebalance + hysteresis | +8.9% / 0.77 / -19% | +8.7% / 0.76 / -17% | +10.2% / 0.84 / -17% |
| + mean-reversion sleeve 25% | +8.7% / 0.76 / -16% | +8.3% / 0.73 / -16% | +11.3% / 0.94 / -15% |
| include 1-month lookback | +9.3% / 0.80 / -18% | +7.7% / 0.68 / -18% | +11.7% / 0.96 / -16% |
| equal weights instead of inverse-vol | +10.0% / 0.79 / -17% | +10.0% / 0.79 / -17% | +12.5% / 0.94 / -17% |

_Past performance is not a promise of future results._
