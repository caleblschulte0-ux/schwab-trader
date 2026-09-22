# Executor run — 2026-09-22 SIM

```
=== Executor | SIM | preset=balanced | 2026-09-22 23:12Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,000.00 cash=$1,000.00 hwm=$1,000.00 managed_capital=$1,000.00 | 1248 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 1/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'QQQ', 'EEM'] --
  strategy: tranche 2/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'QQQ', 'EEM'] --
  strategy: tranche 3/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'QQQ', 'EEM'] --
  strategy: tranche 4/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'QQQ', 'EEM'] --
  strategy: tranche 5/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'QQQ', 'EEM'] --
  momentum holdings: ['DBC', 'EEM', 'QQQ', 'SMH', 'USO', 'XBI', 'XLE', 'XLK']
  regime: breadth=0.655
  regime: risk_off=False
  regime: core=QQQ
  regime: exposure=1.0
targets: QQQ 58%, XLE 8%, DBC 8%, EEM 7%, XLK 6%, XBI 6%, SMH 4%, USO 3%
8 order(s):
  BUY QQQ $582.93 -> filled filled_qty=0.779491 avg=747.8338
  BUY XLE $78.83 -> filled filled_qty=1.275342 avg=61.8109
  BUY DBC $77.51 -> filled filled_qty=2.388140 avg=32.4562
  BUY EEM $68.67 -> filled filled_qty=0.993281 avg=69.1345
  BUY XLK $60.53 -> filled filled_qty=0.308248 avg=196.3681
  BUY XBI $59.75 -> filled filled_qty=0.368939 avg=161.9509
  BUY SMH $39.04 -> filled filled_qty=0.064235 avg=607.7638
  BUY USO $30.74 -> filled filled_qty=0.213247 avg=144.1520
done: equity=$999.50 cash=$2.00 positions=['DBC', 'EEM', 'QQQ', 'SMH', 'USO', 'XBI', 'XLE', 'XLK'] max drift vs target=$1.98
```
