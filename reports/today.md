# Executor run — 2026-09-22 SIM

```
=== Executor | SIM | preset=balanced | 2026-09-22 20:53Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,000.00 cash=$1,000.00 hwm=$1,000.00 managed_capital=$1,000.00 | 1386 min to close
(data) broker bars: 35/35 symbols with >=200 bars
(data) live prices for 35/35 symbols
  strategy: tranche 1/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE'] --
  strategy: tranche 2/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE'] --
  strategy: tranche 3/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE'] --
  strategy: tranche 4/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE'] --
  strategy: tranche 5/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE'] --
  momentum holdings: ['DBC', 'SMH', 'USO', 'XBI', 'XLE', 'XLK']
  regime: breadth=0.793
  regime: risk_off=False
  regime: core=QQQ
  regime: exposure=1.0
targets: QQQ 30%, XLE 16%, DBC 16%, XLK 12%, XBI 12%, SMH 8%, USO 7%
7 order(s):
  BUY QQQ $300.00 -> filled filled_qty=0.401159 avg=747.8338
  BUY XLE $158.39 -> filled filled_qty=2.562493 avg=61.8109
  BUY DBC $155.74 -> filled filled_qty=4.798464 avg=32.4562
  BUY XLK $121.63 -> filled filled_qty=0.619398 avg=196.3681
  BUY XBI $120.07 -> filled filled_qty=0.741397 avg=161.9509
  BUY SMH $78.45 -> filled filled_qty=0.129080 avg=607.7638
  BUY USO $63.71 -> filled filled_qty=0.441964 avg=144.1520
done: equity=$999.50 cash=$2.01 positions=['DBC', 'QQQ', 'SMH', 'USO', 'XBI', 'XLE', 'XLK'] max drift vs target=$2.02
```
