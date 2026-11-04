# Executor run — 2026-11-04 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-11-04 20:25Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$953.72 cash=$0.01 hwm=$1,029.15 managed_capital=$953.72 | 35 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 3/5 momentum rebalance: +['XLP', 'XLB', 'XLF'] --
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 55% -> ['BIL']
  momentum holdings: ['DBC', 'SPY', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV']
  regime: breadth=0.621
  regime: risk_off=False
  regime: core=SSO
  regime: credit_stress=True
  regime: exposure=0.45
  regime: defensive=['BIL']
news: risk level 0 | vetoes [] | Markets are rallying after the Democratic midterm win, with yields lower, oil falling on hopes for an end to the Iran war, and no new crisis-grade shock. Paraguay's Ueno Bank failure and the data center stock slide are regional or narrow and don't directly threaten any held ETF.
targets: BIL 55%, SSO 25%, XLV 4%, DBC 4%, XLE 3%, XBI 2%, XLP 2%, XLB 2%, USO 2%, SPY 1%, XLF 1%
6 order(s):
  SELL BIL $15.73 -> filled filled_qty=0.171958 avg=91.3843
  SELL SSO $8.61 -> filled filled_qty=0.123322 avg=69.7476
  SELL XLV $5.84 -> filled filled_qty=0.030743 avg=189.7751
  BUY XLB $14.13 -> filled filled_qty=0.262948 avg=53.7369
  BUY XLF $8.38 -> filled filled_qty=0.141819 avg=59.0895
  BUY XLP $5.95 -> filled filled_qty=0.064606 avg=92.0960
execution cost today: +5.0 bps vs decision prices over 6 fills (backtest assumes 5)
done: equity=$953.70 cash=$1.70 positions=['BIL', 'DBC', 'SPY', 'SSO', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV'] max drift vs target=$4.81
```
