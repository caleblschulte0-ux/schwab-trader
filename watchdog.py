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

DIAGNOSIS, not just detection: a stall has exactly two likely causes (the trigger
stopped firing at all, e.g. cron-job.org or a paused workflow_dispatch — or it IS
firing but bot.py errors out before finishing) and a bare heartbeat age can't tell
them apart. bot.py also stamps `attempted_utc` the moment a real run starts, before
anything that can fail (see bot.py's `_record_attempt`); `updated_utc` only advances
on a full successful run. Comparing the two ages: attempted_utc fresh + updated_utc
stale means the executor IS being triggered and IS failing every time; both stale
means it isn't being triggered at all. That diagnosis is folded into `detail` (and
the `cause` output) so the alert names the likely cause instead of listing both.

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


def _age_min(now_utc: datetime, key: str) -> float | None:
    """Minutes since holdings.json's `key` timestamp. None if the file or that key is
    missing/corrupt (treated as "no evidence of one" by callers)."""
    try:
        with open(HOLDINGS_FILE, encoding="utf-8") as fh:
            ts = json.load(fh).get(key)
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now_utc - dt).total_seconds() / 60
    except Exception:  # noqa: BLE001 - missing/corrupt/unparseable -> no evidence
        return None


def heartbeat_age_min(now_utc: datetime) -> float | None:
    """Minutes since the executor last completed a full holdings write (a SUCCESSFUL
    run). None if the file is missing/corrupt (treated as a stall — better a false
    alarm than silent death)."""
    return _age_min(now_utc, "updated_utc")


def attempt_age_min(now_utc: datetime) -> float | None:
    """Minutes since the executor last STARTED a run (bot.py's `_record_attempt`,
    stamped before anything that can fail). None if never recorded — an older
    holdings.json from before this field existed, or the executor has never run."""
    return _age_min(now_utc, "attempted_utc")


def diagnose_cause(now_utc: datetime, heartbeat_age: float | None) -> str:
    """Which of the two likely causes a stall is, per the watchdog's own docstring:
    the trigger isn't firing at all, or it's firing and bot.py is failing before it
    can write a fresh heartbeat. `attempted_utc` is stamped before any failure-prone
    code runs, so a fresh attempt with a stale heartbeat can only mean the run started
    and then didn't finish; no fresher attempt than the stale heartbeat itself means
    nothing has started recently."""
    attempt_age = attempt_age_min(now_utc)
    if attempt_age is not None and (heartbeat_age is None or attempt_age < heartbeat_age - 0.01):
        return (f"RUNS FAILING — a run started {attempt_age:.1f} min ago but never finished a "
                "holdings write. Check schwab-trader-bot's most recent run logs (a common cause: "
                "an expired SCHWAB_REFRESH_TOKEN in live mode, or an unhandled error before "
                "write_holdings()).")
    return ("NOT BEING TRIGGERED — no run has started more recently than the stale heartbeat "
            "itself. Check whether cron-job.org is still calling schwab-trader-bot, and whether "
            "trader.yml's workflow_dispatch trigger is enabled (not commented out/paused).")


def _emit(stalled: bool, market_open: bool, detail: str, cause: str = "") -> None:
    print(detail)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"stalled={'true' if stalled else 'false'}\n")
            fh.write(f"market_open={'true' if market_open else 'false'}\n")
            fh.write(f"detail={detail}\n")
            fh.write(f"cause={cause}\n")


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
        cause = diagnose_cause(now, age)
        _emit(True, market_open,
              f"STALL — executor last ran {age_txt} ago (threshold {STALL_MIN} min) during "
              f"market hours. Likely cause: {cause}",
              cause=cause)
    else:
        _emit(False, market_open,
              f"OK — executor heartbeat {age_txt} ago (within {STALL_MIN} min).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
