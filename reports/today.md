# Executor run — 2026-11-05 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-11-05 20:38Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$929.59 cash=$1.70 hwm=$1,029.15 managed_capital=$929.59 | 22 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: tranche 4/5 momentum trend-break exit: ['SPY']
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 81% -> ['BIL']
  momentum holdings: ['DBC', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV']
  regime: breadth=0.483
  regime: risk_off=False
  regime: core=None
  regime: credit_stress=True
  regime: exposure=0.194
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | A severe AI-driven tech selloff (S&P down more than 3%, VIX spiking) dominates the day, hurting the 2x S&P position SSO, while Treasuries rally on haven demand. Oil is volatile on Iran-war diplomacy and the Paraguay bank collapse has no direct exposure to the portfolio's ETFs.
targets: BIL 81%, XLV 4%, DBC 4%, XLE 3%, XLP 2%, XBI 2%, USO 2%, XLB 2%, XLF 1%
3 order(s):
  CLOSE SSO $217.65 -> filled filled_qty=3.416801 avg=63.6682
  CLOSE SPY $10.24 -> filled filled_qty=0.013944 avg=733.8429
  BUY BIL $224.89 -> filled filled_qty=2.458332 avg=91.4807
execution cost today: +5.0 bps vs decision prices over 3 fills (backtest assumes 5)
done: equity=$929.36 cash=$4.58 positions=['BIL', 'DBC', 'USO', 'XBI', 'XLB', 'XLE', 'XLF', 'XLP', 'XLV'] max drift vs target=$4.41
```
