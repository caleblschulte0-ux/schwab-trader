# Executor run — 2026-10-14 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-14 17:58Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$981.93 cash=$4.27 hwm=$1,029.15 managed_capital=$981.93 | 121 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 1/5 momentum trend-break exit: ['EEM']
  strategy: tranche 2/5 momentum trend-break exit: ['EEM']
  strategy: tranche 3/5 momentum trend-break exit: ['EEM']
  strategy: tranche 4/5 momentum trend-break exit: ['EEM']
  strategy: tranche 5/5 momentum rebalance: +['QQQ'] -['EEM']
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 52% -> ['BIL']
  momentum holdings: ['DBC', 'QQQ', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.448
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.475
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | Hot CPI, rising yields and rate-hike bets are weighing on QLD and tech, while the Iran war and Hormuz attacks keep oil elevated, which helps XLE, USO and DBC. No fund-specific or new crisis-grade event warrants a veto today.
targets: BIL 52%, QLD 25%, XLV 5%, DBC 4%, XLE 4%, XLK 3%, XBI 3%, SMH 2%, USO 2%, QQQ 1%
11 order(s):
  SELL QLD $232.92 -> filled filled_qty=2.521020 avg=92.2988
  CLOSE EEM $63.46 -> filled filled_qty=0.986191 avg=64.3180
  SELL XLV $53.43 -> filled filled_qty=0.307906 avg=173.3533
  SELL DBC $41.39 -> filled filled_qty=1.239716 avg=33.3533
  SELL XLE $40.40 -> filled filled_qty=0.597467 avg=67.5512
  SELL XBI $29.88 -> filled filled_qty=0.202640 avg=147.3063
  SELL XLK $27.31 -> filled filled_qty=0.143401 avg=190.2548
  SELL SMH $15.68 -> filled filled_qty=0.027723 avg=565.0373
  SELL USO $14.84 -> filled filled_qty=0.096110 avg=154.2527
  BUY BIL $515.51 -> filled filled_qty=5.629943 avg=91.5658
  BUY QQQ $6.54 -> filled filled_qty=0.008980 avg=728.2950
execution cost today: +5.0 bps vs decision prices over 11 fills (backtest assumes 5)
done: equity=$981.41 cash=$1.05 positions=['BIL', 'DBC', 'QLD', 'QQQ', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV'] max drift vs target=$1.52
```
