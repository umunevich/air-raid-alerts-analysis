#!/usr/bin/env python3
"""Thin wrapper around package ingest for backward compatibility."""

from air_raid_alerts.ingest.fetch_vadimkin import main

if __name__ == "__main__":
    raise SystemExit(main())
