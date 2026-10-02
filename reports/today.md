# Executor run — 2026-10-02 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-02 18:22Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,009.13 cash=$0.01 hwm=$1,009.13 managed_capital=$1,009.13 | 97 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  momentum holdings: ['DBC', 'EEM', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.552
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=False
  regime: exposure=1.0
news: risk level 0 | vetoes [] | A soft jobs report lowered October Fed hike odds, the Nasdaq and Nvidia hit record highs, and Treasury yields eased from multi-decade highs. Oil fell on the G7 fuel reserve release despite Hormuz and Iran tensions, which is already priced in and not a new shock, so no action is needed.
targets: QLD 50%, XLV 9%, XLE 7%, DBC 7%, EEM 7%, XLK 6%, XBI 6%, SMH 4%, USO 3%
2 order(s):
  SELL QLD $6.23 -> filled filled_qty=0.063644 avg=97.7911
  BUY XLV $6.06 -> filled filled_qty=0.036556 avg=165.7728
execution cost today: +5.0 bps vs decision prices over 2 fills (backtest assumes 5)
done: equity=$1,009.13 cash=$0.17 positions=['DBC', 'EEM', 'QLD', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV'] max drift vs target=$2.45
```
