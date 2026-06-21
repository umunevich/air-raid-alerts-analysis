"""Data ingestion from upstream sources."""

from air_raid_alerts.ingest.fetch_vadimkin import update_raw_data

__all__ = ["update_raw_data"]
