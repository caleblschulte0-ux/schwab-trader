# Executor run — 2026-09-22 SIM

```
=== Executor | SIM | NO_TRADE | preset=guarded_growth | 2026-09-23 02:15Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,000.00 cash=$1,000.00 hwm=$1,000.00 managed_capital=$1,000.00 | 1065 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 1/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'EEM', 'XLV'] --
  strategy: tranche 2/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'EEM', 'XLV'] --
  strategy: tranche 3/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'EEM', 'XLV'] --
  strategy: tranche 4/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'EEM', 'XLV'] --
  strategy: tranche 5/5 momentum rebalance: +['USO', 'SMH', 'XBI', 'XLK', 'DBC', 'XLE', 'EEM', 'XLV'] --
  momentum holdings: ['DBC', 'EEM', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.655
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=False
  regime: exposure=1.0
news: risk level 0 | vetoes [] | Markets are at record highs with the Nasdaq closing at new peaks on AI/chip strength, while elevated but already-known themes (10-year yield near 5%, tariffs, oil volatility) are being actively priced in without a fresh acute shock. No portfolio is specified, so no vetoes apply.
targets: QLD 50%, XLV 9%, XLE 8%, DBC 8%, EEM 7%, XLK 6%, XBI 6%, SMH 4%, USO 3%
9 order(s):
  [no-trade] would BUY QLD $500.00
  [no-trade] would BUY XLV $89.20
  [no-trade] would BUY XLE $77.87
  [no-trade] would BUY DBC $76.14
  [no-trade] would BUY EEM $67.36
  [no-trade] would BUY XLK $59.41
  [no-trade] would BUY XBI $59.27
  [no-trade] would BUY SMH $38.44
  [no-trade] would BUY USO $32.31
done: equity=$1,000.00 cash=$1,000.00 positions=[] max drift vs target=$0.00
```
