# Executor run — 2026-10-16 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-16 17:22Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$969.77 cash=$1.05 hwm=$1,029.15 managed_capital=$969.77 | 157 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 1/5 momentum trend-break exit: ['SMH', 'XBI']
  strategy: tranche 2/5 momentum trend-break exit: ['SMH', 'XBI']
  strategy: tranche 3/5 momentum trend-break exit: ['SMH', 'XBI']
  strategy: tranche 4/5 momentum rebalance: +['EWJ', 'QQQ', 'SPY'] -['SMH', 'XBI']
  strategy: tranche 5/5 momentum trend-break exit: ['SMH', 'XBI']
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 57% -> ['BIL']
  momentum holdings: ['DBC', 'EWJ', 'QQQ', 'SPY', 'USO', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.448
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.431
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | Oil is above $100 as Iran escalates Hormuz attacks. Tech and AI names are under pressure, with the Nasdaq-100 down about 3.5% on the week, and Fed Chair Warsh gave no new rate signals. None of this is a fresh, crisis-grade shock that justifies a higher level or a veto.
targets: BIL 57%, QLD 25%, XLV 4%, DBC 3%, XLE 3%, XLK 3%, USO 1%, QQQ 1%, SPY 1%, EWJ 1%
9 order(s):
  CLOSE XBI $25.64 -> filled filled_qty=0.177903 avg=144.0280
  CLOSE SMH $19.85 -> filled filled_qty=0.036489 avg=543.8080
  SELL XLV $6.76 -> filled filled_qty=0.038282 avg=176.4067
  SELL XLE $5.20 -> filled filled_qty=0.076584 avg=67.8311
  BUY BIL $36.13 -> filled filled_qty=0.394450 avg=91.5958
  BUY SPY $10.64 -> filled filled_qty=0.013944 avg=763.0750
  BUY QLD $8.02 -> filled filled_qty=0.090940 avg=88.1902
  BUY QQQ $3.55 -> filled filled_qty=0.004989 avg=711.5156
  BUY EWJ skipped: out of cash ($0.00 left)
execution cost today: +5.0 bps vs decision prices over 8 fills (backtest assumes 5)
done: equity=$969.71 cash=$0.12 positions=['BIL', 'DBC', 'QLD', 'QQQ', 'SPY', 'USO', 'XLE', 'XLK', 'XLV'] max drift vs target=$4.25
```
