# Executor run — 2026-11-10 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-11-10 20:26Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$930.13 cash=$1.26 hwm=$1,029.15 managed_capital=$930.13 | 33 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 54% -> ['BIL']
  momentum holdings: ['DBC', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV']
  regime: breadth=0.552
  regime: risk_off=False
  regime: core=SSO
  regime: credit_stress=True
  regime: exposure=0.456
  regime: defensive=['BIL']
news: no verdict for today (overlay off; trading on the strategy alone)
targets: BIL 54%, SSO 25%, XLV 4%, DBC 4%, XLE 3%, XLB 2%, XLP 2%, XBI 2%, USO 2%, XLF 2%
2 order(s):
  SELL BIL $232.48 -> filled filled_qty=2.539773 avg=91.4443
  BUY SSO $232.53 -> filled filled_qty=3.508662 avg=66.2731
execution cost today: +5.0 bps vs decision prices over 2 fills (backtest assumes 5)
done: equity=$929.90 cash=$0.98 positions=['BIL', 'DBC', 'SSO', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV'] max drift vs target=$2.47
```
