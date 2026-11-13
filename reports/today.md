# Executor run — 2026-11-13 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-11-13 20:28Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$933.62 cash=$0.03 hwm=$1,029.15 managed_capital=$933.62 | 32 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 52% -> ['BIL']
  momentum holdings: ['DBC', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV']
  regime: breadth=0.552
  regime: risk_off=False
  regime: core=SSO
  regime: credit_stress=True
  regime: exposure=0.475
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | Bond yields are near 5% on hot inflation, and the Fed is signaling rate hikes. Nvidia's turmoil is hurting tech, which adds risk for the 2x S&P exposure in SSO. Oil is range-bound, with the IEA reporting a supply surplus. I see no ETF-specific event that justifies a veto.
targets: BIL 52%, SSO 25%, DBC 4%, XLV 4%, XLB 3%, XLP 3%, XLE 3%, XLF 2%, XBI 2%, USO 2%
1 order(s):
  BUY XLP skipped: out of cash ($0.03 left)
done: equity=$933.62 cash=$0.03 positions=['BIL', 'DBC', 'SSO', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV'] max drift vs target=$6.98
```
