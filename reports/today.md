# Executor run — 2026-10-28 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-28 18:49Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$982.74 cash=$7.30 hwm=$1,029.15 managed_capital=$982.74 | 71 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 5/5 momentum rebalance: +['SMH', 'XBI'] --
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 50% -> ['BIL']
  momentum holdings: ['DBC', 'EWJ', 'QQQ', 'SMH', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV']
  regime: breadth=0.552
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.5
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | The Fed held rates steady, equities are near highs, and Big Tech earnings are due. The main risk is Middle East escalation lifting oil, which is a mixed exposure for USO, XLE and DBC and not a clear reason to veto any holding.
targets: BIL 50%, QLD 25%, XLV 4%, DBC 4%, EWJ 3%, XLE 3%, QQQ 3%, XLK 3%, XBI 2%, USO 2%, SPY 1%, XLP 1%, SMH 0%
3 order(s):
  SELL BIL $7.76 -> filled filled_qty=0.084614 avg=91.6192
  BUY XBI $7.84 -> filled filled_qty=0.049940 avg=156.9885
  BUY QQQ $6.22 -> filled filled_qty=0.008579 avg=724.9922
execution cost today: +5.0 bps vs decision prices over 3 fills (backtest assumes 5)
done: equity=$982.73 cash=$0.99 positions=['BIL', 'DBC', 'EWJ', 'QLD', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV'] max drift vs target=$4.07
```
