"""Docker healthcheck: freshness of the pulse file, and nothing else.

Exit 0 - the bot wrote its pulse recently, so it is running.
Exit 1 - the pulse is missing or stale, so it is not.

This check deliberately never contacts Telegram. A neighbouring EZS bot did
exactly that on 19.08.2026: its watchdog read an unreachable Telegram as a dead
process and restarted it 27 times in 40 minutes, turning a passing outage into
an outage of its own. Telegram going down is not this bot's failure - it keeps
running and retrying, and the pulse keeps ticking.

The mark is informational. Nothing may restart the container because of it.
"""
import os
import sys

from health import health_path, is_stale, read_health


def main() -> int:
    path = health_path(os.getenv("DATA_DIR", "./data"))
    health = read_health(path)
    if is_stale(health):
        print(f"stale or missing pulse: {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
