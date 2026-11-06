# Executor run — 2026-11-06 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-11-06 19:56Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$929.85 cash=$4.58 hwm=$1,029.15 managed_capital=$929.85 | 63 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 2/5 momentum rebalance: +['XLB', 'XLF'] --
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 79% -> ['BIL']
  momentum holdings: ['DBC', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV']
  regime: breadth=0.448
  regime: risk_off=False
  regime: core=None
  regime: credit_stress=True
  regime: exposure=0.206
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | Tech and AI stocks sold off hard on Thursday and have partly rebounded. Oil is falling sharply on Iran peace hopes, which matters for the portfolio's energy holdings (XLE, USO, DBC), but this is priced-in price action and not a reason for vetoes. The Paraguay bank collapse and the midterm results don't directly hit any held ETF.
targets: BIL 79%, DBC 4%, XLV 4%, XLE 3%, XLB 2%, XLP 2%, XBI 2%, USO 2%, XLF 2%
3 order(s):
  SELL BIL $11.58 -> filled filled_qty=0.126536 avg=91.4243
  BUY XLB $7.70 -> filled filled_qty=0.147648 avg=52.1511
  BUY XLF $7.19 -> filled filled_qty=0.125199 avg=57.4287
execution cost today: +5.0 bps vs decision prices over 3 fills (backtest assumes 5)
done: equity=$929.83 cash=$1.26 positions=['BIL', 'DBC', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV'] max drift vs target=$2.81
```
