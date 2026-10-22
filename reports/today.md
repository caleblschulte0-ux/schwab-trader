# Executor run — 2026-10-22 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-22 17:57Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$965.98 cash=$0.02 hwm=$1,029.15 managed_capital=$965.98 | 122 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 2/5 momentum rebalance: +['XBI', 'EWJ', 'XLP'] --
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 53% -> ['BIL']
  momentum holdings: ['DBC', 'EWJ', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV']
  regime: breadth=0.517
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.469
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | Stocks are falling as AI-spending worries (Meta) hit tech and oil rises to a five-month high on renewed Iran and Saudi attacks, while Treasury yields fall below 5% on safe-haven demand. This is a risk-off day that markets are already pricing, with no single new event large enough to justify a higher risk level or a veto.
targets: BIL 53%, QLD 25%, XLV 4%, DBC 3%, XLE 3%, XLK 3%, EWJ 2%, QQQ 2%, USO 1%, SPY 1%, XBI 1%, XLP 1%
5 order(s):
  SELL BIL $23.82 -> filled filled_qty=0.259900 avg=91.5592
  BUY QLD $10.69 -> filled filled_qty=0.123694 avg=86.4232
  BUY XBI $8.77 -> filled filled_qty=0.058139 avg=150.8454
  BUY XLP $4.30 -> filled filled_qty=0.048034 avg=89.5197
  BUY EWJ skipped: out of cash ($0.00 left)
execution cost today: +5.0 bps vs decision prices over 4 fills (backtest assumes 5)
done: equity=$965.95 cash=$0.05 positions=['BIL', 'DBC', 'EWJ', 'QLD', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLP', 'XLV'] max drift vs target=$7.32
```
