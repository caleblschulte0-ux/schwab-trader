# Executor run — 2026-09-22 SIM

```
=== Executor | SIM | preset=balanced | 2026-09-22 19:41Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,000.00 cash=$1,000.00 hwm=$1,000.00 managed_capital=$1,000.00 | 18 min to close
(data) Alpaca bars: 35/35 symbols with >=200 bars
(data) live prices for 35/35 symbols
  strategy: momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE'] --
  momentum holdings: ['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE']
  regime: breadth=0.793
  regime: risk_off=False
  regime: exposure=1.0
targets: SPY 30%, XLE 16%, DBC 16%, XLK 12%, XBI 12%, SMH 8%, USO 7%
7 order(s):
  BUY SPY $300.00 -> filled filled_qty=0.387153 avg=774.8872
  BUY XLE $158.62 -> filled filled_qty=2.565176 avg=61.8359
  BUY DBC $155.58 -> filled filled_qty=4.806870 avg=32.3662
  BUY XLK $121.77 -> filled filled_qty=0.620316 avg=196.3031
  BUY XBI $119.91 -> filled filled_qty=0.738857 avg=162.2911
  BUY SMH $78.54 -> filled filled_qty=0.129309 avg=607.3836
  BUY USO $63.57 -> filled filled_qty=0.443796 avg=143.2416
done: equity=$999.50 cash=$2.01 positions=['DBC', 'SMH', 'SPY', 'USO', 'XBI', 'XLE', 'XLK'] max drift vs target=$2.01
```
