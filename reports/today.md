# Executor run — 2026-11-03 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-11-03 20:04Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$946.91 cash=$1.42 hwm=$1,029.15 managed_capital=$946.91 | 56 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 57% -> ['BIL']
  momentum holdings: ['DBC', 'SPY', 'USO', 'XBI', 'XLB', 'XLE', 'XLP', 'XLV']
  regime: breadth=0.483
  regime: risk_off=False
  regime: core=SSO
  regime: credit_stress=True
  regime: exposure=0.431
  regime: defensive=['BIL']
news: no verdict for today (overlay off; trading on the strategy alone)
targets: BIL 57%, SSO 25%, XLV 4%, DBC 4%, XLE 3%, XBI 2%, USO 2%, XLP 2%, SPY 1%, XLB 1%
1 order(s):
  BUY XLB $1.41 -> filled filled_qty=0.026795 avg=52.6213
execution cost today: +5.0 bps vs decision prices over 1 fills (backtest assumes 5)
done: equity=$946.91 cash=$0.01 positions=['BIL', 'DBC', 'SPY', 'SSO', 'USO', 'XBI', 'XLB', 'XLE', 'XLP', 'XLV'] max drift vs target=$5.85
```
