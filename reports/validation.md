# Validation report

_Same engine as `backtest.py`: close fills, 5 bps slippage/side, $0 commissions, dividends reinvested._

## 1. Walk-forward (out-of-sample) test

Parameters chosen on **2008-01-01 → 2016-12-31** only (best Sharpe among 48 combinations), then run untouched on **2017-01-01 → today**.

| Parameter set | In-sample CAGR | In-sample Sharpe | **Out-of-sample CAGR** | **Out-of-sample Sharpe** | OOS Max DD | OOS SPY CAGR |
|---|---:|---:|---:|---:|---:|---:|
| Best in-sample: top 4, lookbacks [126, 252], rebalance 5d | +7.7% | 0.65 | +13.4% | 0.89 | -19.6% | +15.0% |
| Shipped defaults: top 8, lookbacks [63, 126, 252], rebalance 10d | +6.2% | 0.57 | +12.7% | 0.93 | -18.0% | +15.0% |

If the out-of-sample Sharpe collapsed relative to in-sample, the edge was fitted. A modest decay is normal; a similar number means the rules generalise.

## 2. Parameter sensitivity (full period Sharpe)

| top_n \ lookbacks | [63, 126, 252] | [21, 63, 126, 252] | [126, 252] | [63, 126] | [252] |
|---|---:|---:|---:|---:|---:|
| **3** | 0.78 | 0.74 | 0.75 | 0.57 | 0.73 |
| **4** | 0.78 | 0.73 | 0.78 | 0.60 | 0.74 |
| **5** | 0.76 | 0.77 | 0.77 | 0.58 | 0.73 |
| **6** | 0.77 | 0.77 | 0.76 | 0.60 | 0.71 |
| **7** | 0.77 | 0.76 | 0.74 | 0.62 | 0.68 |
| **8** | **0.77** | 0.76 | 0.76 | 0.64 | 0.69 |

A robust strategy shows a plateau, not a single spike. The shipped cell is bold.

## 3. Rebalance-timing luck

Same rules, weekly cycle started on five different days:

| Start | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| 2008-01-02 | +9.6% | 0.77 | -17.8% |
| 2008-01-03 | +9.4% | 0.76 | -18.0% |
| 2008-01-04 | +9.8% | 0.79 | -17.8% |
| 2008-01-07 | +9.6% | 0.77 | -18.0% |
| 2008-01-08 | +9.7% | 0.78 | -17.8% |

Sharpe spread across start days: 0.76 – 0.79.

## 4. Block-bootstrap: what a random 5-year stretch could look like

1000 synthetic 5-year paths built from the strategy's own daily returns (21-day blocks, order shuffled).

| Percentile | 5-yr CAGR | Max drawdown |
|---|---:|---:|
| 5th (bad luck) | +0.8% | -29.7% |
| 25th | +6.2% | -21.7% |
| median | +9.7% | -17.4% |
| 75th | +13.7% | -13.9% |
| 95th (good luck) | +18.9% | -10.8% |

Probability a 5-year stretch would trip a 20% kill switch: **33%** of paths; a 30% kill switch: **5%**. That is why the executor's default `MAX_DRAWDOWN_HALT` is 0.30: a halt at 20% would fire inside the strategy's normal drawdown range and sell the bottom. Probability of a negative 5-year CAGR: **4%**.

## 5. Rolling 3-year windows vs SPY

Across 190 overlapping 3-year windows the strategy beat SPY buy-and-hold in **10%** of them. Median annualised gap -3.1%; worst -18.5%; best +7.7%.

This is the number to internalise: it will trail SPY in most straight-up 3-year stretches, and win by a lot in the stretches that include a bear market.

## 6. Building blocks and overlays, switched one at a time

Everything below is implemented in `strategy.py`; the shipped default is the row marked ✅. Each row flips ONE thing relative to the shipped defaults (`python backtest.py --grid3` for more).

| Variant | 2008→ CAGR / Sharpe / MaxDD | 2015→ CAGR / Sharpe / MaxDD | OOS 2017→ CAGR / Sharpe / MaxDD |
|---|---|---|---|
| ✅ Shipped defaults | +9.6% / 0.77 / -18% | +11.0% / 0.85 / -18% | +12.7% / 0.93 / -18% |
| previous defaults (core 30%, top 6, 200-day) | +10.1% / 0.78 / -20% | +10.6% / 0.80 / -18% | +12.8% / 0.91 / -18% |
| no core sleeve (100% rotation) | +8.4% / 0.73 / -14% | +8.6% / 0.74 / -15% | +10.6% / 0.87 / -15% |
| fixed SPY core instead of adaptive | +8.6% / 0.79 / -17% | +8.7% / 0.80 / -16% | +10.6% / 0.93 / -16% |
| 'growth' preset: fixed QQQ core | +11.0% / 0.88 / -18% | +12.3% / 0.95 / -18% | +14.5% / 1.06 / -18% |
| 'aggressive' preset: 50% in 2x SPY/QQQ (SSO/QLD), trend-timed | +15.1% / 0.81 / -28% | +16.7% / 0.85 / -28% | +19.0% / 0.92 / -28% |
| aggressive + 15% vol cap (rejected) | +10.3% / 0.78 / -23% | +10.8% / 0.79 / -23% | +12.1% / 0.86 / -23% |
| single rebalance tranche (no stagger) | +9.4% / 0.76 / -18% | +10.5% / 0.81 / -19% | +12.9% / 0.94 / -17% |
| no cluster cap | +9.6% / 0.77 / -18% | +11.0% / 0.85 / -18% | +12.7% / 0.93 / -18% |
| top 5 / weekly (previous defaults) | +10.3% / 0.78 / -19% | +11.6% / 0.85 / -18% | +13.4% / 0.92 / -18% |
| defensive asset by momentum (TLT/IEF/GLD) | +10.2% / 0.75 / -26% | +11.6% / 0.84 / -26% | +13.9% / 0.95 / -26% |
| breadth regime switch (<40% → all defensive) | +8.9% / 0.75 / -20% | +10.5% / 0.86 / -15% | +11.9% / 0.91 / -15% |
| portfolio vol target 12% | +8.0% / 0.77 / -16% | +8.6% / 0.79 / -16% | +9.8% / 0.87 / -16% |
| daily rebalance + hysteresis | +9.6% / 0.77 / -19% | +11.0% / 0.85 / -17% | +12.7% / 0.93 / -17% |
| + mean-reversion sleeve 25% | +9.0% / 0.73 / -18% | +10.5% / 0.81 / -18% | +12.2% / 0.90 / -18% |
| include 1-month lookback | +9.5% / 0.76 / -18% | +10.3% / 0.80 / -18% | +11.9% / 0.88 / -18% |
| equal weights instead of inverse-vol | +10.3% / 0.79 / -19% | +11.6% / 0.86 / -20% | +13.2% / 0.93 / -20% |

_Past performance is not a promise of future results._
