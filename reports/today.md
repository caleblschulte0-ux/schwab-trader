# Executor run — 2026-10-20 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-20 17:57Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$976.19 cash=$0.12 hwm=$1,029.15 managed_capital=$976.19 | 122 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 3/5 momentum rebalance: +['XBI', 'EWJ', 'QQQ'] --
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 55% -> ['BIL']
  momentum holdings: ['DBC', 'EWJ', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.517
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.45
  regime: defensive=['BIL']
news: no verdict for today (overlay off; trading on the strategy alone)
targets: BIL 55%, QLD 25%, XLV 4%, DBC 3%, XLE 3%, XLK 3%, QQQ 2%, USO 1%, EWJ 1%, SPY 1%, XBI 0%
3 order(s):
  SELL BIL $14.87 -> filled filled_qty=0.162273 avg=91.5442
  BUY EWJ $13.94 -> filled filled_qty=0.145751 avg=95.6428
  BUY QQQ $1.00 -> filled filled_qty=0.001389 avg=719.8997
execution cost today: +5.0 bps vs decision prices over 3 fills (backtest assumes 5)
done: equity=$976.18 cash=$0.03 positions=['BIL', 'DBC', 'EWJ', 'QLD', 'QQQ', 'SPY', 'USO', 'XLE', 'XLK', 'XLV'] max drift vs target=$10.24
```
