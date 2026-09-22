# Validation report

_Same engine as `backtest.py`: close fills, 5 bps slippage/side, $0 commissions, dividends reinvested._

## 1. Walk-forward (out-of-sample) test

Parameters chosen on **2008-01-01 → 2016-12-31** only (best Sharpe among 60 combinations), then run untouched on **2017-01-01 → today**.

| Parameter set | In-sample CAGR | In-sample Sharpe | **Out-of-sample CAGR** | **Out-of-sample Sharpe** | OOS Max DD | OOS SPY CAGR |
|---|---:|---:|---:|---:|---:|---:|
| Best in-sample: top 6, lookbacks [63, 126, 252], rebalance 5d | +6.8% | 0.62 | +12.3% | 0.95 | -15.2% | +15.4% |
| Shipped defaults: top 6, lookbacks [63, 126, 252], rebalance 10d | +6.8% | 0.61 | +12.3% | 0.95 | -15.8% | +15.4% |

If the out-of-sample Sharpe collapsed relative to in-sample, the edge was fitted. A modest decay is normal; a similar number means the rules generalise.

## 2. Parameter sensitivity (full period Sharpe)

| top_n \ lookbacks | [63, 126, 252] | [21, 63, 126, 252] | [126, 252] | [63, 126] | [252] |
|---|---:|---:|---:|---:|---:|
| **3** | 0.71 | 0.71 | 0.74 | 0.55 | 0.74 |
| **4** | 0.75 | 0.72 | 0.76 | 0.60 | 0.79 |
| **5** | 0.79 | 0.74 | 0.80 | 0.61 | 0.78 |
| **6** | **0.81** | 0.78 | 0.78 | 0.63 | 0.76 |
| **7** | 0.81 | 0.79 | 0.78 | 0.66 | 0.76 |
| **8** | 0.80 | 0.79 | 0.76 | 0.70 | 0.75 |

A robust strategy shows a plateau, not a single spike. The shipped cell is bold.

## 3. Rebalance-timing luck

Same rules, weekly cycle started on five different days:

| Start | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| 2008-01-02 | +9.8% | 0.81 | -17.1% |
| 2008-01-03 | +9.4% | 0.78 | -16.7% |
| 2008-01-04 | +9.9% | 0.81 | -17.1% |
| 2008-01-07 | +9.6% | 0.79 | -16.7% |
| 2008-01-08 | +9.9% | 0.81 | -17.1% |

Sharpe spread across start days: 0.78 – 0.81.

## 4. Block-bootstrap: what a random 5-year stretch could look like

1000 synthetic 5-year paths built from the strategy's own daily returns (21-day blocks, order shuffled).

| Percentile | 5-yr CAGR | Max drawdown |
|---|---:|---:|
| 5th (bad luck) | +1.4% | -26.3% |
| 25th | +6.4% | -19.1% |
| median | +9.8% | -15.6% |
| 75th | +13.4% | -13.0% |
| 95th (good luck) | +18.2% | -10.2% |

Probability a 5-year stretch would trip a 20% kill switch: **20%** of paths; a 30% kill switch: **2%**. That is why the executor's default `MAX_DRAWDOWN_HALT` is 0.30: a halt at 20% would fire inside the strategy's normal drawdown range and sell the bottom. Probability of a negative 5-year CAGR: **3%**.

## 5. Rolling 3-year windows vs SPY

Across 189 overlapping 3-year windows the strategy beat SPY buy-and-hold in **8%** of them. Median annualised gap -4.4%; worst -19.4%; best +10.2%.

This is the number to internalise: it will trail SPY in most straight-up 3-year stretches, and win by a lot in the stretches that include a bear market.

## 6. Building blocks and overlays, switched one at a time

Everything below is implemented in `strategy.py`; the shipped default is the row marked ✅. Each row flips ONE thing relative to the shipped defaults (`python backtest.py --grid3` for more).

| Variant | 2008→ CAGR / Sharpe / MaxDD | 2015→ CAGR / Sharpe / MaxDD | OOS 2017→ CAGR / Sharpe / MaxDD |
|---|---|---|---|
| ✅ Shipped defaults | +9.8% / 0.81 / -17% | +10.3% / 0.84 / -16% | +12.3% / 0.95 / -16% |
| no core sleeve (100% rotation) | +9.5% / 0.74 / -18% | +9.2% / 0.72 / -17% | +11.4% / 0.83 / -17% |
| fixed SPY core instead of adaptive | +9.4% / 0.81 / -17% | +9.3% / 0.81 / -15% | +11.2% / 0.93 / -15% |
| 'growth' preset: fixed QQQ core | +10.1% / 0.84 / -17% | +10.7% / 0.86 / -16% | +13.0% / 1.00 / -16% |
| single rebalance tranche (no stagger) | +9.7% / 0.80 / -18% | +9.9% / 0.81 / -17% | +13.1% / 1.01 / -15% |
| no cluster cap | +10.0% / 0.80 / -20% | +10.6% / 0.83 / -17% | +12.7% / 0.94 / -17% |
| top 5 / weekly (previous defaults) | +9.9% / 0.78 / -18% | +10.8% / 0.84 / -15% | +13.0% / 0.95 / -15% |
| defensive asset by momentum (TLT/IEF/GLD) | +10.1% / 0.77 / -21% | +10.5% / 0.80 / -22% | +13.1% / 0.94 / -22% |
| breadth regime switch (<40% → all defensive) | +9.3% / 0.81 / -19% | +10.7% / 0.91 / -13% | +12.8% / 1.03 / -13% |
| portfolio vol target 12% | +8.4% / 0.79 / -15% | +8.2% / 0.77 / -16% | +9.8% / 0.88 / -16% |
| daily rebalance + hysteresis | +9.1% / 0.76 / -19% | +9.5% / 0.78 / -17% | +11.1% / 0.86 / -17% |
| + mean-reversion sleeve 25% | +9.3% / 0.77 / -16% | +9.9% / 0.81 / -17% | +12.0% / 0.93 / -17% |
| include 1-month lookback | +9.4% / 0.78 / -17% | +9.9% / 0.81 / -15% | +11.9% / 0.92 / -15% |
| equal weights instead of inverse-vol | +10.3% / 0.78 / -18% | +10.9% / 0.81 / -18% | +13.0% / 0.92 / -18% |

_Past performance is not a promise of future results._
