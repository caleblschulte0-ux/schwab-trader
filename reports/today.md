# Executor run — 2026-10-30 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-30 18:34Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$952.86 cash=$0.99 hwm=$1,029.15 managed_capital=$952.86 | 86 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 1/5 momentum trend-break exit: ['XLK', 'EWJ', 'QQQ']
  strategy: tranche 2/5 momentum trend-break exit: ['XLK', 'EWJ']
  strategy: tranche 3/5 momentum trend-break exit: ['XLK', 'EWJ', 'QQQ']
  strategy: tranche 4/5 momentum rebalance: +['XBI', 'XLP', 'XLB'] -['XLK', 'EWJ', 'QQQ']
  strategy: tranche 5/5 momentum trend-break exit: ['XLK', 'QQQ', 'SMH']
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 57% -> ['BIL']
  momentum holdings: ['DBC', 'SPY', 'USO', 'XBI', 'XLB', 'XLE', 'XLP', 'XLV']
  regime: breadth=0.379
  regime: risk_off=False
  regime: core=SSO
  regime: credit_stress=True
  regime: exposure=0.431
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | Tech and chip stocks are being hit hard by AI-spending fears after weak Amazon, Intel and Alphabet results, which matters for the QLD, QQQ and XLK positions. Fed officials are signaling more rate hikes and oil is rising on shipping attacks, but nothing here is crisis-grade or a fund-specific problem that calls for a veto.
targets: BIL 57%, SSO 25%, XLV 4%, DBC 4%, XLE 3%, XBI 2%, USO 2%, XLP 2%, SPY 1%, XLB 1%
8 order(s):
  CLOSE QLD $220.25 -> filled filled_qty=2.715085 avg=81.0794
  CLOSE EWJ $28.01 -> filled filled_qty=0.303968 avg=92.1089
  CLOSE QQQ $27.49 -> filled filled_qty=0.040160 avg=684.2371
  CLOSE XLK $23.72 -> filled filled_qty=0.133981 avg=176.9415
  BUY SSO $238.21 -> filled filled_qty=3.540123 avg=67.2886
  BUY BIL $50.34 -> filled filled_qty=0.548660 avg=91.7509
  BUY XLP $10.34 -> filled filled_qty=0.115190 avg=89.7649
  BUY XLB skipped: out of cash ($0.82 left)
execution cost today: +5.0 bps vs decision prices over 7 fills (backtest assumes 5)
done: equity=$952.56 cash=$1.42 positions=['BIL', 'DBC', 'SPY', 'SSO', 'USO', 'XBI', 'XLE', 'XLP', 'XLV'] max drift vs target=$4.92
```
