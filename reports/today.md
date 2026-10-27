# Executor run — 2026-10-27 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-27 18:40Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$978.27 cash=$0.04 hwm=$1,029.15 managed_capital=$978.27 | 80 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 51% -> ['BIL']
  momentum holdings: ['DBC', 'EWJ', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV']
  regime: breadth=0.552
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.487
  regime: defensive=['BIL']
news: no verdict for today (overlay off; trading on the strategy alone)
targets: BIL 51%, QLD 25%, XLV 4%, DBC 4%, XLE 3%, EWJ 3%, QQQ 3%, XLK 3%, USO 2%, XBI 1%, SPY 1%, XLP 1%
1 order(s):
  SELL QLD $7.26 -> filled filled_qty=0.080555 avg=90.0350
execution cost today: +5.0 bps vs decision prices over 1 fills (backtest assumes 5)
done: equity=$978.26 cash=$7.30 positions=['BIL', 'DBC', 'EWJ', 'QLD', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV'] max drift vs target=$4.95
```
