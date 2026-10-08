# Executor run — 2026-10-08 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-08 19:15Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$1,005.41 cash=$6.89 hwm=$1,029.15 managed_capital=$1,005.41 | 44 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  momentum holdings: ['DBC', 'EEM', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.483
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=False
  regime: exposure=1.0
news: risk level 1 | vetoes [] | Oil is spiking on tanker attacks in Hormuz and Gulf supply fears, while Treasury yields sit at 24-year highs and the Fed is signaling more hikes, which pressures QLD and tech. Yields eased after a strong auction and TSMC reported record revenue, and nothing new is specific enough to veto an ETF.
targets: QLD 50%, XLV 10%, XLE 7%, DBC 7%, EEM 7%, XLK 6%, XBI 6%, SMH 4%, USO 3%
2 order(s):
  SELL XLE $6.12 -> filled filled_qty=0.093538 avg=65.3623
  BUY QLD $8.73 -> filled filled_qty=0.089923 avg=97.0835
execution cost today: +5.0 bps vs decision prices over 2 fills (backtest assumes 5)
done: equity=$1,005.40 cash=$4.27 positions=['DBC', 'EEM', 'QLD', 'SMH', 'USO', 'XBI', 'XLE', 'XLK', 'XLV'] max drift vs target=$3.48
```
