# Executor run — 2026-10-21 SIM

```
=== Executor | SIM | preset=guarded_growth | 2026-10-21 18:00Z ===
no ALPACA_API_KEY/SECRET: trading the built-in simulator (signals/sim_account.json) at Yahoo prices. Add Alpaca keys (SETUP.md) to trade a real paper/live account.
account: equity=$981.23 cash=$0.03 hwm=$1,029.15 managed_capital=$981.23 | 120 min to close
(data) broker bars: 37/37 symbols with >=200 bars
(data) live prices for 37/37 symbols
  strategy: credit stress (HYG/IEF below 50d avg): risk exposure x0.50
  strategy: defensive 55% -> ['BIL']
  momentum holdings: ['DBC', 'EWJ', 'QQQ', 'SPY', 'USO', 'XBI', 'XLE', 'XLK', 'XLV']
  regime: breadth=0.586
  regime: risk_off=False
  regime: core=QLD
  regime: credit_stress=True
  regime: exposure=0.45
  regime: defensive=['BIL']
news: risk level 1 | vetoes [] | US stocks are rallying on strong earnings (SpaceX, Supermicro) while oil stays elevated around $100 on Iran/Hormuz supply risk and inflation fears keep yields near 5%. There is no concrete new event that directly hits a held ETF, so no vetoes.
targets: BIL 55%, QLD 25%, XLV 4%, DBC 3%, XLE 3%, XLK 3%, QQQ 2%, USO 1%, EWJ 1%, SPY 1%, XBI 0%
2 order(s):
  SELL QLD $7.21 -> filled filled_qty=0.078493 avg=91.7641
  BUY QQQ $7.22 -> filled filled_qty=0.009932 avg=726.9233
execution cost today: +5.0 bps vs decision prices over 2 fills (backtest assumes 5)
done: equity=$981.22 cash=$0.02 positions=['BIL', 'DBC', 'EWJ', 'QLD', 'QQQ', 'SPY', 'USO', 'XLE', 'XLK', 'XLV'] max drift vs target=$3.57
```
