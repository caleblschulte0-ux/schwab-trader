# Executor run — 2026-10-01 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-01 18:51Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,002.18 cash=$2.01 hwm=$1,004.64 managed_capital=$1,002.18 | 69 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  momentum holdings: ['DBC', 'EEM', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.448
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=False
  regime: exposure=1.0
news: risk level 1 | vetoes [] | Surging Treasury yields (24-year high), rate-hike expectations and a global bond sell-off are pressuring equities, which matters most for the leveraged Nasdaq position (QLD). China's fuel export suspension is lifting oil, which helps the energy and commodity holdings, and no ETF-specific shock calls for a veto.
targets: QLD 50%, XLV 9%, XLE 8%, DBC 7%, EEM 7%, XLK 6%, XBI 6%, SMH 4%, USO 3%
1 order(s):
  BUY XLV $2.00 -> filled filled_qty=0.012005 avg=166.5932
execution cost today: +5.0 bps vs decision prices over 1 fills (backtest assumes 5)
done: equity=$1,002.17 cash=$0.01 positions=['DBC', 'EEM', 'QLD', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV'] max drift vs target=$4.87
```
