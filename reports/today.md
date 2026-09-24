# Executor run — 2026-09-24 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-09-24 17:51Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,000.00 cash=$1,000.00 hwm=$1,000.00 managed_capital=$1,000.00 | 128 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  momentum holdings: ['DBC', 'EEM', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.586
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=False
  regime: exposure=1.0
news: risk level 1 | vetoes [] | The dominant fresh story is a synchronized global bond selloff driving multi-decade-high yields, which is pressuring rate-sensitive growth/tech stocks and is the main risk to this QLD/XLK/SMH-heavy book today. Middle East oil-supply headlines (Houthi strike on Saudi Arabia, Iran diesel-export-ban talk) are moving crude but appear already reflected in oil prices, so no ETF-specific veto is warranted.
targets: QLD 50%, XLV 9%, DBC 8%, XLE 8%, EEM 7%, XLK 6%, XBI 6%, SMH 4%, USO 3%
9 order(s):
  BUY QLD $500.00 -> filled filled_qty=5.220686 avg=95.7729
  BUY XLV $88.86 -> filled filled_qty=0.523399 avg=169.7748
  BUY DBC $78.20 -> filled filled_qty=2.352473 avg=33.2416
  BUY XLE $77.96 -> filled filled_qty=1.237529 avg=62.9965
  BUY EEM $66.32 -> filled filled_qty=0.986191 avg=67.2486
  BUY XLK $59.14 -> filled filled_qty=0.304348 avg=194.3171
  BUY XBI $58.77 -> filled filled_qty=0.380543 avg=154.4372
  BUY SMH $38.41 -> filled filled_qty=0.064212 avg=598.1789
  BUY USO $30.33 -> filled filled_qty=0.197433 avg=153.6220
execution cost today: +5.0 bps vs decision prices over 9 fills (backtest assumes 5)
done: equity=$999.50 cash=$2.01 positions=['DBC', 'EEM', 'QLD', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV'] max drift vs target=$2.00
```
