#!/usr/bin/env python3
"""Build processed artifacts for one region (default: kyiv_city)."""

from air_raid_alerts.cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(["process", *sys.argv[1:]]))
