# Local dashboard — paste this whole block into a Colab cell and run it.
# It pulls your latest picks/positions/report straight from the repo and draws
# a dashboard INSIDE the Colab output. Private to you, nothing published.
# Re-run the cell anytime to refresh.

import json, urllib.request, datetime
from IPython.display import HTML, display

RAW = "https://raw.githubusercontent.com/caleblschulte0-ux/schwab-trader/main/"

def grab(path):
    try:
        req = urllib.request.Request(RAW + path + "?t=" + str(datetime.datetime.now().timestamp()))
        return urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
    except Exception:
        return None

orders_raw    = grab("signals/orders.json")
positions_raw = grab("signals/positions.md")
report_raw    = grab("reports/today.md")
latest_raw    = grab("signals/latest.md")

# --- build orders table ---
orders_html = "<div style='color:#8b949e'>No orders file yet.</div>"
gen = "?"
if orders_raw:
    try:
        d = json.loads(orders_raw)
        gen = d.get("generated_utc", "?")
        if d.get("orders"):
            rows = ""
            for o in d["orders"]:
                if o.get("action") == "SELL":
                    rows += f"<tr><td style='font-weight:700'>{o['symbol']}</td><td style='color:#f85149'>SELL (close)</td><td colspan=3 style='color:#8b949e'>exit signal</td></tr>"
                else:
                    cost = o.get("quantity",0)*o.get("limit_price",0)
                    rows += (f"<tr><td style='font-weight:700'>{o['symbol']}</td>"
                             f"<td style='color:#3fb950'>BUY {o.get('quantity')}</td>"
                             f"<td>${o.get('limit_price')}</td>"
                             f"<td>🎯 ${o.get('take_profit','-')}</td>"
                             f"<td>🛑 ${o.get('stop_loss','-')} · ${cost:.2f}</td></tr>")
            orders_html = ("<table style='width:100%;border-collapse:collapse'>"
                           "<tr style='color:#8b949e;font-size:12px'><th align=left>Symbol</th><th align=left>Action</th>"
                           "<th align=left>Limit</th><th align=left>Target</th><th align=left>Stop · Cost</th></tr>"
                           + rows + "</table>")
        else:
            orders_html = "<div style='color:#8b949e'>No active orders — HOLD.</div>"
    except Exception as e:
        orders_html = f"<div style='color:#f85149'>parse error: {e}</div>"

def block(title, body):
    return (f"<div style='background:#161b22;border:1px solid #30363d;border-radius:12px;"
            f"padding:14px 16px;margin-bottom:14px'>"
            f"<div style='color:#8b949e;font-size:12px;text-transform:uppercase;"
            f"letter-spacing:.5px;margin-bottom:10px'>{title}</div>{body}</div>")

def pre(text, empty):
    if not text:
        return f"<div style='color:#8b949e'>{empty}</div>"
    safe = text.replace("<", "&lt;")
    return (f"<pre style='white-space:pre-wrap;font-size:13px;color:#e6edf3;background:#0d1117;"
            f"border:1px solid #30363d;border-radius:8px;padding:12px;line-height:1.45'>{safe}</pre>")

html = f"""
<div style='font-family:-apple-system,Segoe UI,sans-serif;background:#0d1117;color:#e6edf3;
            padding:16px;border-radius:14px'>
  <div style='font-size:20px;font-weight:700'>📈 Schwab Bot Dashboard</div>
  <div style='color:#8b949e;font-size:13px;margin:2px 0 14px'>
     Picks generated: {gen} ·
     <span style='background:#1f6feb33;color:#58a6ff;border:1px solid #1f6feb55;
                  padding:2px 8px;border-radius:10px;font-size:12px'>DRY-RUN · paper</span></div>
  {block("Current Orders", orders_html)}
  {block("Open Positions", pre(positions_raw, "No positions file yet — appears after the next run."))}
  {block("Today's Report", pre(report_raw, "No report yet — appears after the market close."))}
  {block("Latest Reasoning", pre(latest_raw, "No reasoning file yet."))}
  <div style='color:#8b949e;font-size:12px;text-align:center;margin-top:8px'>
     Re-run this cell to refresh.</div>
</div>
"""
display(HTML(html))
