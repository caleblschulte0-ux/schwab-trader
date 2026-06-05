"""Executor watchdog — alerts if bot.py stops running during market hours.

WHY THIS EXISTS: the trader (bot.py) is triggered by an EXTERNAL cron
(cron-job.org). On 2026-06-05 that trigger silently stopped and the executor was
dead for the first ~4.5h of the session — managed stops gapped THROUGH their
levels (NVTS sold at $25.61 vs its $27 stop) and nobody was told for hours. This
watchdog is the backstop.

KEY DESIGN CHOICE: it runs on GitHub's OWN scheduler (see watchdog.yml), NOT the
same external cron that drives the trader — so a cron-job.org outage cannot also
take down the alarm that's supposed to catch it.

HEARTBEAT: every executor run rewrites signals/holdings.json with a fresh
`updated_utc` and commits it, so that timestamp's AGE == minutes since the
executor last ran. (Only bot.py writes that file; the brain never touches it, so
it's a clean executor-only heartbeat.) If the age exceeds STALL_MIN while the US
market is open, we flag a stall and the workflow opens a GitHub issue. This also
catches the OTHER failure mode — bot.py erroring on every run — because a crashing
executor never writes a fresh heartbeat either.

Pure stdlib (zoneinfo gives correct US market hours incl. DST). Prints a human-
readable status and, in CI, writes `stalled` / `market_open` / `detail` to
$GITHUB_OUTPUT for the workflow to act on. Exit code is always 0 — the workflow
(not the exit code) decides whether to alert.

Test hooks (unset in prod): WATCHDOG_NOW (ISO time to treat as "now"),
WATCHDOG_HOLDINGS_FILE (alternate heartbeat file), WATCHDOG_STALL_MIN.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timezone

HOLDINGS_FILE  = os.environ.get("WATCHDOG_HOLDINGS_FILE", "signals/holdings.json")
STALL_MIN      = int(os.environ.get("WATCHDOG_STALL_MIN", "20"))  # executor runs ~every 5 min; 20 = ~4 missed runs
OPEN_GRACE_MIN = 10   # don't alarm in the first 10 min after the open (cron + runner spin-up slack)


def _market_tz():
    """US market timezone (handles EDT/EST automatically); falls back to UTC."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001 - some hosts lack tz data; degrade to UTC
        return timezone.utc


def _now() -> datetime:
    override = os.environ.get("WATCHDOG_NOW")  # test hook; unset in prod
    if override:
        dt = datetime.fromisoformat(override.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def is_market_open(now_utc: datetime) -> bool:
    """True during the US regular session (Mon-Fri, 09:30-16:00 ET, DST-aware)."""
    et = now_utc.astimezone(_market_tz())
    if et.weekday() >= 5:  # Sat/Sun
        return False
    return time(9, 30) <= et.time() <= time(16, 0)


def in_alarm_window(now_utc: datetime) -> bool:
    """Market open, minus a spin-up grace right after the open (avoids false alarms
    while the cron + runner are still warming up at 09:30)."""
    if not is_market_open(now_utc):
        return False
    et = now_utc.astimezone(_market_tz())
    minutes_since_open = (et.hour - 9) * 60 + (et.minute - 30)
    return minutes_since_open >= OPEN_GRACE_MIN


def heartbeat_age_min(now_utc: datetime) -> float | None:
    """Minutes since the executor last wrote holdings.json. None if the file is
    missing/corrupt (treated as a stall — better a false alarm than silent death)."""
    try:
        with open(HOLDINGS_FILE, encoding="utf-8") as fh:
            ts = json.load(fh).get("updated_utc")
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now_utc - dt).total_seconds() / 60
    except Exception:  # noqa: BLE001 - missing/corrupt/unparseable -> stall
        return None


def _emit(stalled: bool, market_open: bool, detail: str) -> None:
    print(detail)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"stalled={'true' if stalled else 'false'}\n")
            fh.write(f"market_open={'true' if market_open else 'false'}\n")
            fh.write(f"detail={detail}\n")


def main() -> int:
    now = _now()
    market_open = is_market_open(now)
    age = heartbeat_age_min(now)
    age_txt = "unknown (heartbeat file missing/corrupt)" if age is None else f"{age:.1f} min"

    if not in_alarm_window(now):
        _emit(False, market_open,
              f"OK (outside alarm window) — market_open={market_open}; last executor run {age_txt} ago.")
        return 0

    stalled = age is None or age > STALL_MIN
    if stalled:
        _emit(True, market_open,
              f"STALL — executor last ran {age_txt} ago (threshold {STALL_MIN} min) during market hours.")
    else:
        _emit(False, market_open,
              f"OK — executor heartbeat {age_txt} ago (within {STALL_MIN} min).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
