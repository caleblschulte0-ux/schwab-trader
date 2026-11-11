# Executor run — 2026-11-11 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-11-11 20:14Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$937.76 cash=$0.98 hwm=$1,029.15 managed_capital=$937.76 | 46 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 1/5 momentum rebalance: +['XLP', 'XLB', 'XLF'] --
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 52% -> ['BIL']
  momentum holdings: ['DBC', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV']
  regime: breadth=0.586
  regime: risk_off=False
  regime: core=SSO
  regime: credit_stress=True
  regime: exposure=0.475
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | Rate-hike fears after a hot October CPI dominate, with the dollar at a 19-month high and yields up, while AI worries eased on CoreWeave results and stocks rebounded. Oil is choppy on Iran/Hormuz headlines and Paraguay's bank collapse is local, so no vetoes are warranted for this portfolio.
targets: BIL 52%, SSO 25%, DBC 4%, XLV 4%, XLB 3%, XLP 3%, XLE 3%, XLF 2%, XBI 2%, USO 2%
4 order(s):
  SELL BIL $13.60 -> filled filled_qty=0.148563 avg=91.4522
  BUY XLF $7.37 -> filled filled_qty=0.125673 avg=58.6443
  BUY XLB $7.17 -> filled filled_qty=0.135075 avg=53.0815
  BUY XLP skipped: out of cash ($0.00 left)
execution cost today: +5.0 bps vs decision prices over 3 fills (backtest assumes 5)
done: equity=$937.74 cash=$0.03 positions=['BIL', 'DBC', 'SSO', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV'] max drift vs target=$7.09
```
