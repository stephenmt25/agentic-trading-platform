"""Reporting domain — generators for paper-trading daily reports etc."""

from libs.reports.daily import backfill, generate_for_date

__all__ = ["generate_for_date", "backfill"]
