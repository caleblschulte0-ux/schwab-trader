"""Daily heartbeat check: did the executor complete a trading-window run today?

Runs on GitHub's OWN scheduler (independent of whatever triggers the bot) after the
close on weekdays. Reads signals/state.json (which bot.py commits every run) and
flags a stall if `last_trade_date` != today (ET) on a trading day. Exit code is
always 0; the workflow reads `stalled` / `detail` from $GITHUB_OUTPUT.

Test hooks: WATCHDOG_NOW (ISO datetime treated as now, UTC), WATCHDOG_STATE_FILE.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def main() -> int:
    now_s = os.environ.get("WATCHDOG_NOW")
    now = datetime.fromisoformat(now_s).astimezone(timezone.utc) if now_s else datetime.now(timezone.utc)
    now_et = now.astimezone(ET)
    today = now_et.strftime("%Y-%m-%d")
    path = os.environ.get("WATCHDOG_STATE_FILE", "signals/state.json")
    try:
        with open(path) as f:
            st = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        st = {}

    trading_day = now_et.weekday() < 5
    # Optional precise check via Alpaca's calendar when keys are present.
    key, sec = os.environ.get("ALPACA_API_KEY", "").strip(), os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if key and sec and trading_day:
        try:
            from alpaca import Alpaca
            cal = Alpaca(key, sec, paper=True).calendar(today, today)
            trading_day = any(c.get("date") == today for c in cal)
        except Exception as exc:  # noqa: BLE001
            print(f"(watchdog) calendar check failed ({exc}); assuming weekday = trading day")

    stalled = False
    warn = False
    detail = ""
    if not trading_day:
        detail = f"{today} is not a trading day; nothing expected."
    elif st.get("halted"):
        detail = f"Executor is intentionally HALTED ({st.get('halt_reason')}). Not a stall."
    elif st.get("last_trade_date") == today:
        detail = f"OK: executor completed its trading-window run today ({st.get('last_run_utc')})."
    elif st.get("last_seen_date") == today:
        warn = True
        detail = (f"The executor RAN today ({st.get('last_run_utc')}) but did not complete a trading-window step "
                  "(market closed early? stale data? refused live?). Read reports/today.md.")
    else:
        stalled = True
        detail = (f"No executor run recorded for {today}. last_seen_date={st.get('last_seen_date')}, "
                  f"last_run_utc={st.get('last_run_utc')}. Check the trader workflow's recent runs / schedule.")
    print(f"(watchdog) stalled={stalled} warn={warn} :: {detail}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"stalled={'true' if stalled else 'false'}\n")
            f.write(f"warn={'true' if warn else 'false'}\n")
            f.write(f"detail={detail}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
