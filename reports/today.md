# Executor run — 2026-10-26 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-26 19:14Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$973.70 cash=$0.05 hwm=$1,029.15 managed_capital=$973.70 | 46 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 1/5 momentum rebalance: +['XBI', 'EWJ', 'QQQ'] --
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 51% -> ['BIL']
  momentum holdings: ['DBC', 'EWJ', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV']
  regime: breadth=0.448
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.487
  regime: defensive=['BIL']
news: no verdict for today (overlay off; trading on the strategy alone)
targets: BIL 51%, QLD 25%, XLV 4%, DBC 4%, XLE 3%, EWJ 3%, QQQ 3%, XLK 3%, USO 2%, XBI 1%, SPY 1%, XLP 1%
4 order(s):
  SELL BIL $14.40 -> filled filled_qty=0.157047 avg=91.6007
  SELL XLK $5.04 -> filled filled_qty=0.026966 avg=186.7166
  BUY EWJ $14.94 -> filled filled_qty=0.158217 avg=94.4272
  BUY QQQ $4.49 -> filled filled_qty=0.006290 avg=713.8281
execution cost today: +5.0 bps vs decision prices over 4 fills (backtest assumes 5)
done: equity=$973.69 cash=$0.04 positions=['BIL', 'DBC', 'EWJ', 'QLD', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV'] max drift vs target=$4.81
```
